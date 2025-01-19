#!/bin/bash

# Copyright 2020 The FedLearner Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -ex

export CUDA_VISIBLE_DEVICES=
source /app/deploy/scripts/hdfs_common.sh || true
source /app/deploy/scripts/pre_start_hook.sh || true
source /app/deploy/scripts/env_to_args.sh

UPLOAD_DIR=$OUTPUT_BASE_DIR/upload
spark_entry_script="fedlearner/data_join/raw_data/raw_data.py"
push_file $spark_entry_script $UPLOAD_DIR
# create deps folder structure
DEP_FILE=deps.zip
CUR_DIR=`pwd`
TMP_DIR=`mktemp -d`
TMP_FEDLEARNER_DIR=${TMP_DIR}/fedlearner/data_join/raw_data
mkdir -p $TMP_FEDLEARNER_DIR
cp fedlearner/data_join/raw_data/common.py $TMP_FEDLEARNER_DIR
cd $TMP_DIR
touch fedlearner/__init__.py
touch fedlearner/data_join/__init__.py
touch fedlearner/data_join/raw_data/__init__.py
python /app/deploy/scripts/zip.py ${DEP_FILE} fedlearner
push_file ${DEP_FILE} ${UPLOAD_DIR}
cd $CUR_DIR
rm -rf $TMP_DIR

input_file_wildcard=$(normalize_env_to_args "--input_file_wildcard" "$FILE_WILDCARD")
kvstore_type=$(normalize_env_to_args '--kvstore_type' $KVSTORE_TYPE)
input_format=$(normalize_env_to_args '--input_format' $INPUT_DATA_FORMAT)
files_per_job_limit=$(normalize_env_to_args '--files_per_job_limit' $FILES_PER_JOB_LIMIT)
output_type=$(normalize_env_to_args '--output_type' $OUTPUT_TYPE)
output_format=$(normalize_env_to_args '--output_format' $OUTPUT_DATA_FORMAT)
data_block_dump_threshold=$(normalize_env_to_args '--data_block_dump_threshold' $DATA_BLOCK_DUMP_THRESHOLD)
spark_image=$(normalize_env_to_args '--spark_image' $SPARK_IMAGE)
spark_driver_cores=$(normalize_env_to_args '--spark_driver_cores' $SPARK_DRIVER_CORES)
spark_driver_memory=$(normalize_env_to_args '--spark_driver_memory' $SPARK_DRIVER_MEMORY)
spark_executor_cores=$(normalize_env_to_args '--spark_executor_cores' $SPARK_EXECUTOR_CORES)
spark_executor_memory=$(normalize_env_to_args '--spark_executor_memory' $SPARK_EXECUTOR_MEMORY)
spark_executor_instances=$(normalize_env_to_args '--spark_executor_instances' $SPARK_EXECUTOR_INSTANCES)
validation=$(normalize_env_to_args '--validation' $VALIDATION)
start_date=$(normalize_env_to_args '--start_date' $START_DATE)
end_date=$(normalize_env_to_args '--end_date' $END_DATE)
oss_access_key_id=$(normalize_env_to_args '--oss_access_key_id' $OSS_ACCESS_KEY_ID)
oss_access_key_secret=$(normalize_env_to_args '--oss_access_key_secret' $OSS_ACCESS_KEY_SECRET)
oss_endpoint=$(normalize_env_to_args '--oss_endpoint' $OSS_ENDPOINT)

python -m fedlearner.data_join.cmd.raw_data_cli \
    --data_portal_name=$DATA_PORTAL_NAME \
    --data_portal_type=$DATA_PORTAL_TYPE \
    --output_partition_num=$OUTPUT_PARTITION_NUM \
    --input_base_dir=$INPUT_BASE_DIR \
    --output_base_dir=$OUTPUT_BASE_DIR \
    --raw_data_publish_dir=$RAW_DATA_PUBLISH_DIR \
    --upload_dir=$UPLOAD_DIR \
    --web_console_url=$WEB_CONSOLE_V2_ENDPOINT \
    --web_console_username=$ROBOT_USERNAME \
    --web_console_password=$ROBOT_PWD \
    --spark_dependent_package=$UPLOAD_DIR/${DEP_FILE} \
    $input_file_wildcard $input_format $LONG_RUNNING $CHECK_SUCCESS_TAG $kvstore_type \
    $SINGLE_SUBFOLDER $files_per_job_limit $output_type $output_format \
    $data_block_dump_threshold \
    $spark_image $spark_driver_cores $spark_driver_memory \
    $spark_executor_cores $spark_executor_memory $spark_executor_instances \
    $validation $start_date $end_date \
    $oss_access_key_id $oss_access_key_secret $oss_endpoint
