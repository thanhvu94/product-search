FROM apache/airflow:2.7.1-python3.10

USER root
RUN apt-get update && \
    apt-get install -y git && \
    apt-get install -y libgomp1 && \
    apt-get install -y openjdk-17-jre-headless

# Download jars libs to run Spark
RUN mkdir -p /opt/airflow/spark_jars && chown -R airflow:root /opt/airflow/spark_jars
RUN curl -o /opt/airflow/spark_jars/hadoop-aws.jar https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.4.0/hadoop-aws-3.4.0.jar && \
    curl -o /opt/airflow/spark_jars/aws-sdk-bundle.jar https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.700/aws-java-sdk-bundle-1.12.700.jar && \
    curl -o /opt/airflow/spark_jars/postgresql.jar https://repo1.maven.org/maven2/org/postgresql/postgresql/42.5.4/postgresql-42.5.4.jar

USER airflow

# Set Java path so Spark can find it
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"
ENV PYTHONPATH="${PYTHONPATH}:/opt/airflow/scripts"

# Install required libs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# This is to fix a bug in Airflow with PostgreSQL connection
RUN pip install git+https://github.com/mpgreg/airflow-provider-great-expectations.git@87a42e275705d413cd4482134fc0d94fa1a68e6f

# Requirement for running Docker Operator
RUN pip install apache-airflow-providers-docker==3.7.5