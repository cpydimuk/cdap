.. meta::
    :author: Cask Data, Inc.
    :copyright: Copyright © 2014-2018 Cask Data, Inc.

.. _cdap-building-running:

======================================
Building and Running CDAP Applications
======================================

.. |example| replace:: <example>
.. |example-dir| replace:: <example-directory>


.. highlight:: console

In the examples, we refer to the CDAP Sandbox as *CDAP*, and the example code that is
running on it as an *application*. We'll assume that you are running your application in
the *default* :ref:`namespace <namespaces>`; if not, you will need to adjust commands
accordingly. For example, in a URL such as::

	http://localhost:11015/v3/namespaces/default/apps...

to use the namespace *my_namespace*, you would replace ``default`` with ``my_namespace``::

	http://localhost:11015/v3/namespaces/my_namespace/apps...


Accessing CLI, curl, and the CDAP Sandbox bin
---------------------------------------------------

- For brevity in the commands given below, we will simply use ``cdap cli`` for the CDAP
  Command Line Interface. Substitute the actual path of ``./<CDAP-HOME>/bin/cdap cli``,
  or ``<CDAP-HOME>\bin\cdap.bat cli`` on Windows, as appropriate.

- A Windows-version of the application ``curl`` is included in the CDAP Sandbox as
  ``libexec\bin\curl.exe``; use it as a substitute for ``curl`` in examples.

- If you add the CDAP Sandbox ``bin`` directory to your path, you can simplify the commands. From within
  the ``<CDAP-HOME>`` directory, enter:

  .. tabbed-parsed-literal::

    .. Linux

    $ export PATH=${PATH}:\`pwd\`/bin

    .. Windows

    > set path=%PATH%;%CD%\bin;%CD%\libexec\bin

  The Windows path has been augmented with a directory where the CDAP Sandbox includes
  Windows-versions of commands such as ``curl``.

.. include:: /_includes/windows-note.txt

.. _cdap-building-running-example:

Building an Example Application Artifact
----------------------------------------

From the example's project root (such as ``examples/<example-dir>``), build an example with the
`Apache Maven <http://maven.apache.org>`__ command:

.. tabbed-parsed-literal::

  $ mvn clean package

To build without running tests, use:

.. tabbed-parsed-literal::

  $ mvn clean package -DskipTests

To build all the examples, switch to the main examples directory and run the Maven command:

.. tabbed-parsed-literal::

  $ cd <CDAP-HOME>/examples
  $ mvn clean package -DskipTests


.. _cdap-building-running-starting:

Starting CDAP
-------------

Before running an example application, check that an instance of CDAP is running and available; if not,
follow the instructions for :ref:`Starting and Stopping CDAP Sandbox <start-stop-cdap>`.

If you can reach the CDAP UI through a browser at :cdap-ui:`http://localhost:11011/ <>`,
CDAP is running.

.. _cdap-building-running-deploying:

Deploying an Application
------------------------

Once CDAP is started, there are multiple ways to deploy an application using an example JAR:

- Using the green "plus" button to upload the application's JAR file on the CDAP UI

- Using the :ref:`Command Line Interface (CLI) <cli>`:

  .. tabbed-parsed-literal::

      $ cdap cli load artifact examples/|example-dir|/target/|example|-|release|.jar
      Successfully added artifact with name '|example|'

      $ cdap cli create app <app name> |example| |release| user
      Successfully created application

  The CLI can be accessed under Windows using the ``bin\cdap.bat cli`` script.

- Using an application such as ``curl`` (a Windows-version is included in the CDAP Sandbox in
  ``libexec\bin\curl.exe``):

  .. tabbed-parsed-literal::

    $ curl -w"\n" localhost:11015/v3/namespaces/default/artifacts/|example| \
      --data-binary @examples/|example-dir|/target/|example|-|release|.jar
    Artifact added successfully

    $ curl -w"\n" -X PUT -H "Content-Type: application/json" localhost:11015/v3/namespaces/default/apps/<app name> \
      -d '{ "artifact": { "name": "|example|", "version": "|release|", "scope": "user" }, "config": {} }'
    Deploy Complete


.. _cdap-building-running-starting-application:
.. _cdap-building-running-starting-programs:

Starting an Application's Programs
----------------------------------

Once an application is deployed, there are multiple methods for starting an application's programs:

- The CDAP UI.

- The :ref:`Command Line Interface<cli>` to start a specific program of an application.
  (In each CDAP example, the CLI commands for that particular example are provided):

  .. tabbed-parsed-literal::

    $ cdap cli start <program-type> <app-id.program-id>

  .. list-table::
    :widths: 20 80
    :header-rows: 1

    * - Parameter
      - Description
    * - ``<program-type>``
      - One of ``flow``, ``mapreduce``, ``service``, ``spark``, ``worker``, or ``workflow``
    * - ``<app-id>``
      - Name of the application being called
    * - ``<program-id>``
      - Name of the *flow*, *MapReduce*, *service*, *spark*, *worker* or *workflow* being called

..

- The :ref:`Command Line Interface<cli>` to start all or selected types of programs of an application at once:

  .. tabbed-parsed-literal::

    $ start app <app-id> programs [of type <program-types>]

  .. list-table::
    :widths: 20 80
    :header-rows: 1

    * - Parameter
      - Description
    * - ``<app-id>``
      - Name of the application being called
    * - ``<program-types>``
      - An optional comma-separated list of program types (``flow``, ``mapreduce``, ``service``,
        ``spark``, ``worker``, or ``workflow``) which will start all programs of those
        types; for example, specifying ``'flow,workflow'`` will start all flows and
        workflows in the application

..

- The :ref:`Program Lifecycle <http-restful-api-lifecycle-start>` of the Lifecycle
  HTTP RESTful API to start the programs of an application using a program such as ``curl``

.. _cdap-building-running-stopping:
.. _cdap-building-running-stopping-application:
.. _cdap-building-running-stopping-program:

Stopping an Application's Programs
----------------------------------

Once an application is deployed, there are multiple ways for stopping an application's programs:

- The CDAP UI.

- The :ref:`Command Line Interface <cli>` to stop a specific program of an application:

  .. tabbed-parsed-literal::

    $ cdap cli stop <program-type> <app-id.program-id>

  .. list-table::
    :widths: 20 80
    :header-rows: 1

    * - Parameter
      - Description
    * - ``<program-type>``
      - One of ``flow``, ``mapreduce``, ``service``, ``spark``, ``worker``, or ``workflow``
    * - ``<app-id>``
      - Name of the application being called
    * - ``<program-id>``
      - Name of the *flow*, *MapReduce*, *service*, *spark*, *worker* or *workflow* being called

..

- The :ref:`Command Line Interface<cli>` to stop all or selected types of programs of an application at once:

  .. tabbed-parsed-literal::

    $ stop app <app-id> programs [of type <program-types>]

  .. list-table::
    :widths: 20 80
    :header-rows: 1

    * - Parameter
      - Description
    * - ``<app-id>``
      - Name of the application being called
    * - ``<program-types>``
      - An optional comma-separated list of program types (``flow``, ``mapreduce``, ``service``,
        ``spark``, ``worker``, or ``workflow``) which will stop all programs of those
        types; for example, specifying ``'flow,workflow'`` will stop all flows and
        workflows in the application

..

- Use the :ref:`Program Lifecycle <http-restful-api-lifecycle-stop>` of the Lifecycle
  HTTP RESTful API to stop the programs of an application using a program such as ``curl``

.. _cdap-building-running-removing:

Removing an Application
-----------------------

Once an application is "stopped" |---| when all of its programs are stopped |---| you can remove the application using
the CDAP UI.

Alternatively, you can also use the Command Line Interface:

.. tabbed-parsed-literal::

  $ cdap cli delete app <app-id>

Note that any datasets created or used by the application will remain, as they
are independent of the application. Datasets can be deleted from the CDAP UI, or by using the
:ref:`HTTP Restful API <restful-api>`, the :ref:`Java Client API <java-client-api>`, or the
:ref:`Command Line Interface API <cli>`.

Streams can be either truncated or deleted, using similar methods.

The artifact used to create the application will also remain, as multiple
applications can be created from the same artifact. Artifacts can be deleted using the UI,
:ref:`Http Restful API <restful-api>`, the
:ref:`Java Client API <java-client-api>`, or the :ref:`Command Line Interface API <cli>`.
