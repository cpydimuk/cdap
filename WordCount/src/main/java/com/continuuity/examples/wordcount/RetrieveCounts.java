package com.continuuity.examples.wordcount;

import com.continuuity.api.annotation.Handle;
import com.continuuity.api.annotation.UseDataSet;
import com.continuuity.api.common.Bytes;
import com.continuuity.api.data.OperationResult;
import com.continuuity.api.data.dataset.KeyValueTable;
import com.continuuity.api.data.dataset.table.Read;
import com.continuuity.api.data.dataset.table.Table;
import com.continuuity.api.procedure.AbstractProcedure;
import com.continuuity.api.procedure.ProcedureRequest;
import com.continuuity.api.procedure.ProcedureResponder;
import com.continuuity.api.procedure.ProcedureResponse;
import com.continuuity.api.procedure.ProcedureResponse.Code;

import java.util.Map;
import java.util.TreeMap;

public class RetrieveCounts extends AbstractProcedure {

  byte[] TOTALS_ROW = Bytes.toBytes("totals");
  byte[] TOTAL_LENGTH = Bytes.toBytes("total_length");
  byte[] TOTAL_WORDS = Bytes.toBytes("total_words");

  @UseDataSet("wordStats")
  private Table wordStatsTable;
  
  @UseDataSet("wordCounts")
  private KeyValueTable wordCountsTable;
  
  @UseDataSet("uniqueCount")
  private UniqueCountTable uniqueCountTable;

  @UseDataSet("wordAssocs")
  private AssociationTable associationTable;

  @Handle("getStats")
  public void getStats(ProcedureRequest request, ProcedureResponder responder) throws Exception {
    // first method is 'getStats' and returns all the global statistics, takes no arguments
    long totalWords = 0L, uniqueWords = 0L;
    double averageLength = 0.0;

    // Read the total_length and total_words to calculate average length
    OperationResult<Map<byte[],byte[]>> result =
      this.wordStatsTable.read(new Read(TOTALS_ROW, new byte[][] { TOTAL_LENGTH, TOTAL_WORDS }));
    if (!result.isEmpty()) {
      // extract the total sum of lengths
      byte[] lengthBytes = result.getValue().get(TOTAL_LENGTH);
      Long totalLength = lengthBytes == null ? 0L : Bytes.toLong(lengthBytes);
      // extract the total count of words
      byte[] wordsBytes = result.getValue().get(TOTAL_WORDS);
      totalWords = wordsBytes == null ? 0L : Bytes.toLong(wordsBytes);
      // compute the average length
      if (totalLength != 0 && totalWords != 0) {
        averageLength = (double)totalLength/(double)totalWords;
        // Read the unique word count
        uniqueWords = this.uniqueCountTable.readUniqueCount();
      }
    }

    // return a map as JSON
    Map<String, Object> results = new TreeMap<String, Object>();
    results.put("totalWords", totalWords);
    results.put("uniqueWords", uniqueWords);
    results.put("averageLength", averageLength);
    responder.sendJson(new ProcedureResponse(Code.SUCCESS), results);
  }

  @Handle("getCount")
  public void getCount(ProcedureRequest request, ProcedureResponder responder) throws Exception {
    // second method is 'getCount' with argument of word='', optional limit=#
    // returns count of word and top words associated with that word,
    // up to specified limit (default limit = 10 if not specified)
    String word = request.getArgument("word");
    if (word == null) {
      responder.error(Code.CLIENT_ERROR, "Method 'getCount' requires argument 'word'");
      return;
    }

    String limitArg = request.getArgument("limit");
    int limit = limitArg == null ? 10 : Integer.valueOf(limitArg);

    // Read the word count
    byte[] countBytes = this.wordCountsTable.read(Bytes.toBytes(word));
    Long wordCount = countBytes == null ? 0L : Bytes.toLong(countBytes);

    // Read the top associated words
    Map<String,Long> wordsAssocs = this.associationTable.readWordAssocs(word, limit);

    // return a map as JSON
    Map<String, Object> results = new TreeMap<String, Object>();
    results.put("word", word);
    results.put("count", wordCount);
    results.put("assocs", wordsAssocs);
    responder.sendJson(new ProcedureResponse(Code.SUCCESS), results);
  }

  @Handle("getAssoc")
  public void getAssoc(ProcedureRequest request, ProcedureResponder responder) throws Exception {
    // third method is 'getAssoc' with argument of word1, word2
    // returns number of times the two words co-occurred
    String word1 = request.getArgument("word1");
    String word2 = request.getArgument("word2");
    if (word1 == null || word2 == null) {
      responder.error(Code.CLIENT_ERROR, "Method 'getCount' requires arguments 'word1' and 'word2'");
      return;
    }

    // Read the top associated words
    long count = this.associationTable.getAssoc(word1, word2);

    // return a map as JSON
    Map<String, Object> results = new TreeMap<String, Object>();
    results.put("word1", word1);
    results.put("word2", word2);
    results.put("count", count);
    responder.sendJson(new ProcedureResponse(Code.SUCCESS), results);
  }
}
