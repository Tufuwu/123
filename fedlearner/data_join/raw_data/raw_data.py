import argparse
import logging
import json
import os

from cityhash import CityHash32  # pylint: disable=no-name-in-module
from pyspark import SparkFiles
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, IntegerType, LongType
from pyspark.sql.functions import col  # pylint: disable=no-name-in-module

from fedlearner.data_join.raw_data.common import Constants, DataKeyword, \
    JobType, OutputType, FileFormat, RawDataSchema


def set_logger():
    logging.getLogger().setLevel(logging.INFO)
    logging.basicConfig(format="%(asctime)s %(filename)s:%(lineno)s "
                               "%(levelname)s - %(message)s")


def _get_oss_jars():
    spark_jar_path = "/opt/spark/jars"
    dependent_jar_names = ('emr-core', 'aliyun-sdk-oss', 'commons-codec',
                           'httpclient', 'httpcore', 'commons-logging',
                           'jdom')
    dependent_jars = []
    for jar_name in os.listdir(spark_jar_path):
        if jar_name.startswith(dependent_jar_names):
            dependent_jars.append(os.path.join(spark_jar_path, jar_name))
    return ','.join(dependent_jars)


def start_spark(app_name='my_spark_app',
                jar_packages=None,
                files=None,
                spark_config=None,
                oss_access_key_id=None,
                oss_access_key_secret=None,
                oss_endpoint=None):
    # get Spark session factory
    spark_builder = \
        SparkSession.builder.appName(app_name)

    # create Spark JAR packages string
    if jar_packages:
        spark_jars_packages = ','.join(list(jar_packages))
        spark_builder.config('spark.jars', spark_jars_packages)

    if files:
        spark_files = ','.join(list(files))
        spark_builder.config('spark.files', spark_files)

    # ---------- speculation related
    # Re-launches tasks if they are running slowly in a stage
    spark_builder.config('spark.speculation', 'true')
    # Checks tasks to speculate every 100ms
    spark_builder.config('spark.speculation.interval', 100)
    # Fraction of tasks which must be complete before
    # speculation is enabled for a particular stage.
    spark_builder.config('spark.speculation.quantile', 0.9)
    # How many times slower a task is than the median
    # to be considered for speculation.
    spark_builder.config('spark.speculation.multiplier', 2)
    # ---------- end of speculation related

    if spark_config:
        # add other config params
        for key, val in spark_config.items():
            spark_builder.config(key, val)

    if oss_access_key_id and oss_access_key_secret and oss_endpoint:
        spark_builder.config("spark.hadoop.fs.oss.core.dependency.path",
                             _get_oss_jars())
        spark_builder.config("spark.hadoop.fs.oss.accessKeyId",
                             oss_access_key_id)
        spark_builder.config("spark.hadoop.fs.oss.accessKeySecret",
                             oss_access_key_secret)
        spark_builder.config("spark.hadoop.fs.oss.endpoint",
                             oss_endpoint)
        spark_builder.config("spark.hadoop.fs.oss.impl",
                             "com.aliyun.fs.oss.nat.NativeOssFileSystem")

    # create session and retrieve Spark logger object
    return spark_builder.getOrCreate()


def get_config(config_filename):
    # get config file if sent to cluster with --files
    spark_files_dir = SparkFiles.getRootDirectory()
    path_to_config_file = os.path.join(spark_files_dir, config_filename)
    if os.path.exists(path_to_config_file):
        with open(path_to_config_file, 'r') as config_file:
            config_dict = json.load(config_file)
    else:
        config_dict = None
    return config_dict


def validate(data_df, job_type):
    if job_type == JobType.PSI:
        field_names = [DataKeyword.raw_id]
    else:
        field_names = [DataKeyword.example_id, DataKeyword.event_time]
    columns = data_df.columns
    for field_name in field_names:
        if field_name not in columns:
            raise RuntimeError("Field %s which is necessary missed" %
                               field_name)
        if data_df.where(col(field_name).isNull()).count() != 0:
            raise RuntimeError("There are invalid values of field '%s'" %
                               field_name)


class RawData:
    def __init__(self, config_file=None, jar_packages=None,
                 oss_access_key_id=None,
                 oss_access_key_secret=None,
                 oss_endpoint=None):
        # start Spark application and get Spark session, logger and config
        config_files = [config_file] if config_file else None
        self._config = None

        self._spark = start_spark(
            app_name='RawData',
            jar_packages=jar_packages,
            files=config_files,
            oss_access_key_id=oss_access_key_id,
            oss_access_key_secret=oss_access_key_secret,
            oss_endpoint=oss_endpoint)

        if config_file:
            self._config = get_config(os.path.basename(config_file))

    def run(self, config=None):
        set_logger()
        if not config:
            config = self._config
        output_type = config[Constants.output_type_key]

        if output_type == OutputType.DataBlock:
            self._to_data_block(config)
        else:
            self._to_raw_data(config)

    def _to_raw_data(self, config):
        job_type = config[Constants.job_type_key]
        input_files = config[Constants.input_files_key].split(",")
        input_format = config[Constants.input_format_key]
        output_path = config[Constants.output_path_key]
        output_format = config[Constants.output_format_key]
        partition_num = config[Constants.output_partition_num_key]
        validation = config.get(Constants.validation_key, 0)

        logging.info("Deal with new files %s", input_files)

        # read input data
        if input_format == FileFormat.CSV:
            data_df = self._spark.read \
                .format("csv") \
                .option("header", "true") \
                .load(input_files, inferSchema="true")
        else:
            data_df = self._spark.read \
                .format("tfrecords") \
                .option("recordType", "Example") \
                .load(",".join(input_files))

        data_df = self._format_data_frame(data_df, job_type)

        data_df.printSchema()
        if validation:
            validate(data_df, job_type)

        partition_field = self._get_partition_field(job_type)
        if partition_field not in data_df.columns:
            logging.warning("There is no partition field %s in data",
                            partition_field)
            return
        partition_index = data_df.columns.index(partition_field)

        # deal with data
        output_df = self._partition_and_sort(data_df, job_type,
                                             partition_num, partition_index)

        if output_format == FileFormat.CSV:
            output_df.write \
                .mode("overwrite") \
                .format("csv") \
                .save(output_path, header='true')
        else:
            # output data
            write_options = {
                "recordType": "Example",
                "maxRecordsPerFile": 1 << 20,
                "codec": 'org.apache.hadoop.io.compress.GzipCodec',
            }
            output_df.write \
                .mode("overwrite") \
                .format("tfrecords") \
                .options(**write_options) \
                .save(output_path)

        logging.info("Export data to %s finished", output_path)

    def _to_data_block(self, config):
        input_files = config[Constants.input_files_key]
        output_path = config[Constants.output_path_key]
        data_block_threshold = config[Constants.data_block_threshold_key]
        compression_type = config[Constants.compression_type_key]
        if compression_type and compression_type.upper() == "GZIP":
            write_options = {
                "mapred.output.compress": "true",
                "mapred.output.compression.codec":
                    "org.apache.hadoop.io.compress.GzipCodec",
            }
        else:
            write_options = {
                "mapred.output.compress": "false",
            }

        logging.info("Deal with new files %s with write option %s",
                     input_files, write_options)

        data_rdd = self._spark.sparkContext.newAPIHadoopFile(
            input_files,
            "org.tensorflow.hadoop.io.TFRecordFileInputFormat",
            keyClass="org.apache.hadoop.io.BytesWritable",
            valueClass="org.apache.hadoop.io.NullWritable")
        if data_block_threshold > 0:
            num_partition = int((data_rdd.count() + data_block_threshold - 1) /
                                data_block_threshold)

            data_rdd = data_rdd.zipWithIndex()

            data_rdd = data_rdd \
                .keyBy(lambda value: value[1]) \
                .partitionBy(num_partition, partitionFunc=lambda k: k) \
                .map(lambda x: x[1][0])

        data_rdd.saveAsNewAPIHadoopFile(
            output_path,
            "org.tensorflow.hadoop.io.TFRecordFileOutputFormat",
            keyClass="org.apache.hadoop.io.BytesWritable",
            valueClass="org.apache.hadoop.io.NullWritable",
            conf=write_options)

        logging.info("Export data to %s finished", output_path)

    @staticmethod
    def _format_data_frame(data_df, job_type):

        def cast(fname, target_type):
            if target_type == "string":
                return data_df.withColumn(fname, data_df[fname].cast(
                    StringType()))
            if target_type == "integer":
                return data_df.withColumn(fname, data_df[fname].cast(
                    IntegerType()))
            if target_type == "long":
                return data_df.withColumn(fname, data_df[fname].cast(
                    LongType()))
            raise RuntimeError("Do not support type %s of field %s" %
                               (target_type, fname))

        data_schema = data_df.schema
        field_types = {}
        for field in data_schema:
            field_value = field.jsonValue()
            field_types[field_value["name"]] = field_value["type"]
        schema = RawDataSchema.StreamSchema
        if job_type == JobType.PSI:
            schema = RawDataSchema.PSISchema
        for name, field in schema.items():
            if field.required and name not in field_types:
                raise RuntimeError("Field %s is required" % name)
            if name in field_types and \
                field_types[name] not in field.types:
                data_df = cast(name, field.default_type)
        return data_df

    def _partition_and_sort(self, data_df, job_type,
                            partition_num, partition_index):
        def partitioner_fn(x):
            return CityHash32(x)

        schema = data_df.schema

        data_df = data_df.rdd \
            .keyBy(lambda value: value[partition_index]) \
            .partitionBy(int(partition_num), partitionFunc=partitioner_fn) \
            .map(lambda x: x[1]) \
            .toDF(schema=schema)

        if job_type == JobType.Streaming:
            return data_df.sortWithinPartitions(DataKeyword.event_time,
                                                DataKeyword.example_id)
        return data_df.sortWithinPartitions(DataKeyword.raw_id)  # PSI

    @staticmethod
    def _get_partition_field(job_type):
        if job_type == JobType.PSI:
            return DataKeyword.raw_id
        return DataKeyword.example_id

    def stop(self):
        self._spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', type=str, default="config.json")
    parser.add_argument('--packages', type=str, default="")
    parser.add_argument('--oss_access_key_id', type=str, default='',
                        help='access key id for oss')
    parser.add_argument('--oss_access_key_secret', type=str, default='',
                        help='access key secret for oss')
    parser.add_argument('--oss_endpoint', type=str, default='',
                        help='endpoint for oss')
    args = parser.parse_args()
    set_logger()
    logging.info(args)

    packages = args.packages.split(",")
    processor = RawData(args.config, packages,
                        oss_access_key_id=args.oss_access_key_id,
                        oss_access_key_secret=args.oss_access_key_secret,
                        oss_endpoint=args.oss_endpoint)
    processor.run()
    processor.stop()
