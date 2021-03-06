#!/usr/bin/env sh
# Create the image to lmdb inputs

TOOLS=/home/work_dir/caffe-master/build/tools

#图像文件的存放位置
TRAIN_DATA_ROOT=/home/mjd/FaceDetection_CNN/
VAL_DATA_ROOT=/home/mjd/FaceDetection_CNN/

IMAGE_LIST_ROOT=/home/mjd/FaceDetection_CNN/
#LMDB文件的存放位置
ROOT_LMDB=/home/mjd/DeepFace-master/FaceDetection/train_lmdb

# Set RESIZE=true to resize the images to 256x256. Leave as false if images have
# already been resized using another tool.

#是否剪切为相同的大小
RESIZE=true
if $RESIZE; then
  RESIZE_HEIGHT=48  #should align with deploy.prototxt file in detection
  RESIZE_WIDTH=48
else
  RESIZE_HEIGHT=0
  RESIZE_WIDTH=0
fi

if [ ! -d "$TRAIN_DATA_ROOT" ]; then
  echo "Error: TRAIN_DATA_ROOT is not a path to a directory: $TRAIN_DATA_ROOT"
  echo "Set the TRAIN_DATA_ROOT variable in create_imagenet.sh to the path" \
       "where the ImageNet training data is stored."
  exit 1
fi

if [ ! -d "$VAL_DATA_ROOT" ]; then
  echo "Error: VAL_DATA_ROOT is not a path to a directory: $VAL_DATA_ROOT"
  echo "Set the VAL_DATA_ROOT variable in create_imagenet.sh to the path" \
       "where the ImageNet validation data is stored."
  exit 1
fi

echo "Creating train lmdb..."

GLOG_logtostderr=1 $TOOLS/convert_imageset \
    --resize_height=$RESIZE_HEIGHT \
    --resize_width=$RESIZE_WIDTH \
    --shuffle \
    $TRAIN_DATA_ROOT \
    $IMAGE_LIST_ROOT/crop_images_train/aflw_train_rand2.txt \
    $ROOT_LMDB/train
    #--gray \
    
echo "Creating val lmdb..."

GLOG_logtostderr=1 $TOOLS/convert_imageset \
    --resize_height=$RESIZE_HEIGHT \
    --resize_width=$RESIZE_WIDTH \
    --shuffle \
    $VAL_DATA_ROOT \
    $IMAGE_LIST_ROOT/crop_images_val/aflw_val_rand2.txt \
    $ROOT_LMDB/val
    #--gray \

$TOOLS/compute_image_mean $ROOT_LMDB/train \
  $ROOT_LMDB/mean.binaryproto

echo "Done."
