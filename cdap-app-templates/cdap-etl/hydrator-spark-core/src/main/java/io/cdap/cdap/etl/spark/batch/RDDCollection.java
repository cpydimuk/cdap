/*
 * Copyright © 2020 Cask Data, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

package io.cdap.cdap.etl.spark.batch;

import io.cdap.cdap.api.data.DatasetContext;
import io.cdap.cdap.api.data.format.StructuredRecord;
import io.cdap.cdap.api.data.schema.Schema;
import io.cdap.cdap.api.spark.JavaSparkExecutionContext;
import io.cdap.cdap.api.spark.sql.DataFrames;
import io.cdap.cdap.etl.api.join.JoinField;
import io.cdap.cdap.etl.common.Constants;
import io.cdap.cdap.etl.spark.SparkCollection;
import io.cdap.cdap.etl.spark.function.CountingFunction;
import io.cdap.cdap.etl.spark.join.JoinCollection;
import io.cdap.cdap.etl.spark.join.JoinRequest;
import io.cdap.cdap.etl.spark.plugin.LiteralsBridge;
import org.apache.spark.api.java.JavaRDD;
import org.apache.spark.api.java.JavaSparkContext;
import org.apache.spark.api.java.function.Function;
import org.apache.spark.sql.Column;
import org.apache.spark.sql.DataFrame;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SQLContext;
import org.apache.spark.sql.functions;
import org.apache.spark.sql.types.DataType;
import org.apache.spark.sql.types.DataTypes;
import org.apache.spark.sql.types.StructType;
import scala.collection.JavaConversions;
import scala.collection.Seq;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import static org.apache.spark.sql.functions.floor;

/**
 * Spark1 RDD collection.
 *
 * @param <T> type of object in the collection
 */
public class RDDCollection<T> extends BaseRDDCollection<T> {

  public RDDCollection(JavaSparkExecutionContext sec, JavaSparkContext jsc, SQLContext sqlContext,
                       DatasetContext datasetContext, SparkBatchSinkFactory sinkFactory, JavaRDD<T> rdd) {
    super(sec, jsc, sqlContext, datasetContext, sinkFactory, rdd);
  }

  @SuppressWarnings("unchecked")
  @Override
  public SparkCollection<T> join(JoinRequest joinRequest) {
    Map<String, DataFrame> collections = new HashMap<>();
    String stageName = joinRequest.getStageName();
    Function<StructuredRecord, StructuredRecord> recordsInCounter =
      new CountingFunction<>(stageName, sec.getMetrics(), Constants.Metrics.RECORDS_IN, sec.getDataTracer(stageName));
    StructType leftSparkSchema = DataFrames.toDataType(joinRequest.getLeftSchema());
    DataFrame left = toDataFrame(((JavaRDD<StructuredRecord>) rdd).map(recordsInCounter), leftSparkSchema);
    collections.put(joinRequest.getLeftStage(), left);

    List<Column> leftJoinColumns = joinRequest.getLeftKey().stream()
      .map(left::col)
      .collect(Collectors.toList());

    /*
        This flag keeps track of whether there is at least one required stage in the join.
        This is needed in case there is a join like:

        A (optional), B (required), C (optional), D (required)

        The correct thing to do here is:

        1. A right outer join B as TMP1
        2. TMP1 left outer join C as TMP2
        3. TMP2 inner join D

        Join #1 is a straightforward join between 2 sides.
        Join #2 is a left outer because TMP1 becomes 'required', since it uses required input B.
        Join #3 is an inner join even though it contains 2 optional datasets, because 'B' is still required.
     */
    Integer joinPartitions = joinRequest.getNumPartitions();
    boolean seenRequired = joinRequest.isLeftRequired();
    DataFrame joined = left;
    for (JoinCollection toJoin : joinRequest.getToJoin()) {
      RDDCollection<StructuredRecord> data = (RDDCollection<StructuredRecord>) toJoin.getData();
      StructType sparkSchema = DataFrames.toDataType(toJoin.getSchema());
      DataFrame right = toDataFrame(data.rdd.map(recordsInCounter), sparkSchema);
      collections.put(toJoin.getStage(), right);

      List<Column> rightJoinColumns = toJoin.getKey().stream()
        .map(right::col)
        .collect(Collectors.toList());

      String joinType;
      if (seenRequired && toJoin.isRequired()) {
        joinType = "inner";
      } else if (seenRequired && !toJoin.isRequired()) {
        joinType = "leftouter";
      } else if (!seenRequired && toJoin.isRequired()) {
        joinType = "rightouter";
      } else {
        joinType = "outer";
      }
      seenRequired = seenRequired || toJoin.isRequired();

      // UUID for salt column name to avoid name collisions
      String saltColumn = UUID.randomUUID().toString();
      if (joinRequest.isDistributionEnabled()) {

        boolean isLeftStageSkewed =
          joinRequest.getLeftStage().equals(joinRequest.getDistribution().getSkewedStageName());

        // Apply salt/explode transformations to each Dataframe
        if (isLeftStageSkewed) {
          left = saltDataFrame(left, saltColumn, joinRequest.getDistribution().getDistributionFactor());
          right = explodeDataFrame(right, saltColumn, joinRequest.getDistribution().getDistributionFactor());
        } else {
          left = explodeDataFrame(left, saltColumn, joinRequest.getDistribution().getDistributionFactor());
          right = saltDataFrame(right, saltColumn, joinRequest.getDistribution().getDistributionFactor());
        }

        // Add the salt column to the join key
        leftJoinColumns.add(left.col(saltColumn));
        rightJoinColumns.add(right.col(saltColumn));

        // Updating other values that will be used later in join
        joined = left;
        sparkSchema = sparkSchema.add(saltColumn, DataTypes.IntegerType, false);
        leftSparkSchema = leftSparkSchema.add(saltColumn, DataTypes.IntegerType, false);
      }

      Iterator<Column> leftIter = leftJoinColumns.iterator();
      Iterator<Column> rightIter = rightJoinColumns.iterator();
      Column joinOn = eq(leftIter.next(), rightIter.next(), joinRequest.isNullSafe());
      while (leftIter.hasNext()) {
        joinOn = joinOn.and(eq(leftIter.next(), rightIter.next(), joinRequest.isNullSafe()));
      }

      if (toJoin.isBroadcast()) {
        right = functions.broadcast(right);
      }
      // repartition on the join keys with the number of partitions specified in the join request.
      // since they are partitioned on the same thing, spark will not repartition during the join,
      // which allows us to use a different number of partitions per joiner instead of using the global
      // spark.sql.shuffle.partitions setting in the spark conf
      if (joinPartitions != null && !toJoin.isBroadcast()) {
        List<String> rightKeys = new ArrayList<>(toJoin.getKey());
        List<String> leftKeys = new ArrayList<>(joinRequest.getLeftKey());

        // If distribution is enabled we need to add it to the partition keys to ensure we end up with the desired
        // number of partitions
        if (joinRequest.isDistributionEnabled()) {
          rightKeys.add(saltColumn);
          leftKeys.add(saltColumn);
        }
        right = partitionOnKey(right, rightKeys, joinRequest.isNullSafe(), sparkSchema, joinPartitions);
        // only need to repartition the left side if this is the first join,
        // as intermediate joins will already be partitioned on the key
        if (joined == left) {
          joined = partitionOnKey(joined, leftKeys, joinRequest.isNullSafe(),
            leftSparkSchema, joinPartitions);
        }
      }
      joined = joined.join(right, joinOn, joinType);

      /*
           Consider stages A, B, C:

           A (id, email) = (2, charles@example.com)
           B (id, name) = (0, alice), (1, bob)
           C (id, age) = (0, 25)

           where A, B, C are joined on A.id = B.id = C.id, where B and C are required and A is optional.
           This RDDCollection is the data for stage A.

           this is implemented as a join of (A right outer join B on A.id = B.id) as TMP1
           followed by (TMP1 inner join C on TMP1.B.id = C.id) as OUT

           TMP1 looks like:
           TMP1 (A.id, A.name, B.id, B.email) = (null, null, 0, alice), (null, null, 1, bob)

           and the final output looks like:
           OUT (A.id, A.name, B.id, B.email, C.id, C.age) = (null, null, 0, alice, 0, 25)

           It's important to join on B.id = C.id and not on A.id = C.id, because joining on A.id = C.id will result
           in an empty output, as A.id is always null in the TMP1 dataset. In general, the principle is to join on the
           required fields and not on the optional fields when possible.
       */
      if (toJoin.isRequired()) {
        leftJoinColumns = rightJoinColumns;
      }
    }

    // select and alias fields in the expected order
    List<Column> outputColumns = new ArrayList<>(joinRequest.getFields().size());
    for (JoinField field : joinRequest.getFields()) {
      Column column = collections.get(field.getStageName()).col(field.getFieldName());
      if (field.getAlias() != null) {
        column = column.alias(field.getAlias());
      }

      outputColumns.add(column);
    }

    Seq<Column> outputColumnSeq = JavaConversions.asScalaBuffer(outputColumns).toSeq();
    joined = joined.select(outputColumnSeq);

    Schema outputSchema = joinRequest.getOutputSchema();
    JavaRDD<StructuredRecord> output = joined.javaRDD()
      .map(r -> DataFrames.fromRow(r, outputSchema))
      .map(new CountingFunction<>(stageName, sec.getMetrics(),
        Constants.Metrics.RECORDS_OUT,
        sec.getDataTracer(stageName)));
    return (SparkCollection<T>) wrap(output);
  }

  /**
   * Helper method that adds a salt column to a dataframe for join distribution
   *
   * @param data               Dataframe add salt to
   * @param saltColumnName     Name to use for the new salt column
   * @param distributionFactor The desired salt size, values in the salt column will range [0,distributionFactor)
   * @return Dataframe with an additional salt column
   */
  private DataFrame saltDataFrame(DataFrame data, String saltColumnName, int distributionFactor) {
    DataFrame saltedData = data.withColumn(saltColumnName, functions.rand().multiply(distributionFactor));
    saltedData = saltedData.withColumn(saltColumnName,
      floor(saltedData.col(saltColumnName)).cast(DataTypes.IntegerType));
    return saltedData;
  }

  /**
   * Helper method that adds salt column to a dataframe and explodes the rows
   *
   * @param data               Dataframe to explode
   * @param saltColumnName     Name to use for the new salt column
   * @param distributionFactor The desired salt size, this will increase the number of rows by a factor of
   *                           distributionFactor
   * @return Dataframe with an additional salt column
   */
  private DataFrame explodeDataFrame(DataFrame data, String saltColumnName, int distributionFactor) {
    //Array of [0,distributionFactor) to be used in to prepare for the explode
    Integer[] numbers = IntStream.range(0, distributionFactor).boxed().toArray(Integer[]::new);

    // Add a column that uses the 'numbers' array as the value for every row
    DataFrame explodedData = data.withColumn(saltColumnName,
      functions.array(
        Arrays.stream(numbers).map(functions::lit).toArray(Column[]::new)
      ));
    explodedData = explodedData.withColumn(saltColumnName, functions.explode(explodedData.col(saltColumnName)));
    return explodedData;
  }

  private DataFrame toDataFrame(JavaRDD<StructuredRecord> rdd, StructType sparkSchema) {
    JavaRDD<Row> rowRDD = rdd.map(record -> DataFrames.toRow(record, sparkSchema));
    return sqlContext.createDataFrame(rowRDD.rdd(), sparkSchema);
  }

  private DataFrame partitionOnKey(DataFrame df, List<String> key, boolean isNullSafe, StructType sparkSchema,
                                   int numPartitions) {
    List<Column> columns = getPartitionColumns(df, key, isNullSafe, sparkSchema);
    return df.repartition(numPartitions, JavaConversions.asScalaBuffer(columns).toSeq());
  }

  private List<Column> getPartitionColumns(DataFrame df, List<String> key, boolean isNullSafe, StructType sparkSchema) {
    if (!isNullSafe) {
      return key.stream().map(df::col).collect(Collectors.toList());
    }

    // if a null safe join is happening, spark will partition on coalesce(col, [default val]),
    // where the default val is dependent on the column type and defined in
    // org.apache.spark.sql.catalyst.expressions.Literal
    return key.stream().map(keyCol -> {
      int fieldIndex = sparkSchema.fieldIndex(keyCol);
      DataType dataType = sparkSchema.fields()[fieldIndex].dataType();
      Column defaultCol = new Column(LiteralsBridge.defaultLiteral(dataType));
      return functions.coalesce(df.col(keyCol), defaultCol);
    }).collect(Collectors.toList());
  }
}
