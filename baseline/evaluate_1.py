# -*- coding: utf-8 -*-
#study about nms parameters and figure out process of generating bounding boxes
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import sys
import os
from  math import pow
import skimage.io
from skimage import transform as tf

caffe_root = '/home/work_dir/caffe-master/'
sys.path.insert(0, caffe_root + 'python')
import caffe

from nms import nms_average,nms_max

caffe.set_device(0)
caffe.set_mode_gpu()

import logging

_DEBUG = True
import pdb

#============
#Model related:
model_path = '/home/mjd/DeepFace-master/FaceDetection/baseline/'
model_define= model_path+'deploy.prototxt'
model_weight =model_path+'snapshot_iter_100000.caffemodel'
model_define_fc =model_path+'deploy_fc.prototxt'
model_weight_fc =model_path+'snapshot_iter_100000_fc.caffemodel'

channel = 3
raw_scale = 255.0
face_w = 48
stride = 16
cellSize = face_w
threshold = 0.93 # threshold for generate bounding boxes and re_verify, originally 0.95
factor = 0.793700526 # 缩小因子

map_idx = 0
params = ['deepid', 'fc7']
params_fc =  ['deepid-conv', 'fc7-conv']


def generateBoundingBox(featureMap, scale):
    '''
    @brief: 生成窗口
    @param: featureMap,特征图，scale：尺度
    '''
    boundingBox = []
    for (x,y), prob in np.ndenumerate(featureMap):
       if(prob >= threshold):
           #映射到原始的图像中的大小
            x=x-1
            y=y-1
            boundingBox.append([float(stride * y)/scale, float(stride *x )/scale, 
                              float(stride * y + cellSize - 1)/scale, float(stride * x + cellSize - 1)/scale, prob])
            #boundingBox.append([float(stride * y-cellSize/2.0)/scale, float(stride *x -cellSize/2.0)/scale, 
            #                   float(stride * y + cellSize/2.0 - 1)/scale, float(stride * x + cellSize/2.0 - 1)/scale, prob])
    return boundingBox

def convert_full_conv(model_define,model_weight,model_define_fc,model_weight_fc):
    '''
    @breif : 将原始网络转换为全卷积模型
    @param: model_define,二分类网络定义文件
    @param: model_weight，二分类网络训练好的参数
    @param: model_define_fc,生成的全卷积网络定义文件
    @param: model_weight_fc，转化好的全卷积网络的参数
    '''
    net = caffe.Net(model_define, model_weight, caffe.TEST)
    fc_params = {pr: (net.params[pr][0].data, net.params[pr][1].data) for pr in params}
    net_fc = caffe.Net(model_define_fc, model_weight, caffe.TEST)
    conv_params = {pr: (net_fc.params[pr][0].data, net_fc.params[pr][1].data) for pr in params_fc}
    for pr, pr_conv in zip(params, params_fc):
       conv_params[pr_conv][0].flat = fc_params[pr][0].flat  # flat unrolls the arrays
       conv_params[pr_conv][1][...] = fc_params[pr][1]
    net_fc.save(model_weight_fc)
    print 'convert done!'
    return net_fc

def re_verify(net_vf, img):
    '''
    @breif: 对检测到的目标框进行重新的验证
    '''
    img= tf.resize(img,(face_w,face_w))
    transformer = caffe.io.Transformer({'data': net_vf.blobs['data'].data.shape})
    transformer.set_transpose('data', (2,0,1))
    transformer.set_channel_swap('data', (2,1,0))
    transformer.set_raw_scale('data', raw_scale)
    out = net_vf.forward_all(data=np.asarray([transformer.preprocess('data', img)]))
    #print out['prob']
    if out['prob'][0,map_idx] > threshold:
        return True
    else:
        return False

def draw_boxes( true_boxes, imgs, im, fileName ):
    fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(6, 6))
    ax.imshow(imgs)
    for box in true_boxes:
        im_crop = im[box[0]:box[2],box[1]:box[3],:]
        if im_crop.shape[0] == 0 or im_crop.shape[1] == 0:
            continue
        if True:#re_verify(net_vf, im_crop) == True:
            rect = mpatches.Rectangle((box[0], box[1]), box[2]-box[0], box[3]-box[1],
                fill=False, edgecolor='red', linewidth=1)
            ax.text(box[0], box[1]+20,"{0:.3f}".format(box[4]),color='white', fontsize=6)
            ax.add_patch(rect)
    plt.savefig('record1/'+fileName)  
    return ax
          
def face_detection_image(net,net_vf,image_name):
    '''
    @检测单张人脸图像
    '''
    if _DEBUG != True:
        pdb.set_trace()
    scales = []
    imgs = skimage.io.imread(image_name)
    if imgs.ndim==3:
            rows,cols,ch = imgs.shape
    elif imgs.ndim==0:#09437 channel is 0
            return 0
    else :
            rows,cols = imgs.shape #grey image
            imgs = skimage.color.gray2rgb(imgs)
    
    #计算需要的检测的尺度因子
    min = rows if  rows<=cols  else  cols
    max = rows if  rows>=cols  else  cols
    # 放大的尺度    
    delim = 2500/max
    while (delim >= 1):
        scales.append(delim)
        delim=delim-0.5
    #缩小的尺度
    min = min * factor
    factor_count = 1
    while(min >= face_w):
        scale = pow(factor,  factor_count)
        scales.append(scale)
        min = min * factor
        factor_count += 1
    #=========================
    #scales.append(1)
    total_boxes = []
    ###显示热图用
    num_scale = len(scales)
    s1=int(np.sqrt(num_scale))+1
    tt=1
    plt.subplot(s1, s1+1, tt)
    plt.axis('off')
    plt.title("Input Image")
    im=caffe.io.load_image(image_name)
    plt.imshow(im)
    #============
    for scale in scales:
        w,h = int(rows* scale),int(cols* scale)
        scale_img= tf.resize(imgs,(w,h))
        #更改网络输入data图像的大小
        net.blobs['data'].reshape(1,channel,w,h)
        #转换结构
        transformer = caffe.io.Transformer({'data': net.blobs['data'].data.shape})
        #transformer.set_mean('data', np.load(caffe_root + 'python/caffe/imagenet/ilsvrc_2012_mean.npy').mean(1).mean(1))
        transformer.set_transpose('data', (2,0,1))
       # if imgs.ndim==3:#some pictures are in black and white
        transformer.set_channel_swap('data', (2,1,0))
        transformer.set_raw_scale('data', raw_scale)
        #前馈一次
        out = net.forward_all(data=np.asarray([transformer.preprocess('data', scale_img)]))
        ###显示热图用
        tt=tt+1
        plt.subplot(s1, s1+1, tt)
        plt.axis('off')
        plt.title("sacle: "+ "%.2f" %scale)
        heatmap = plt.imshow(out['prob'][0,map_idx])
        plt.colorbar(heatmap) #添加颜色指示条
        #===========       
        boxes = generateBoundingBox(out['prob'][0,map_idx], scale)

        if(boxes):
            total_boxes.extend(boxes)
    #非极大值抑制
    info = image_name.split('/')
    info1 = info[8].split('.')
 
    boxes_total = np.array(total_boxes)
    draw_boxes( boxes_total, imgs, im, info1[0]+'total.jpg')

    #找出每个热图中最大的若干概率值 
   # idxs = np.argsort(boxes_total[:,4])
   # last = len(idxs) - 1
   # i = idxs[last]
    #写入文件
    #fileWriter = open( './result/max_probs.txt', 'a+' )
    #fileWriter.write( image_name )
    #for i in idxs[ last-10 : last ]:
      #fileWriter.write( ' ' )
     # fileWriter.write( str(np.asscalar(boxes_total[i,4])) )
    #fileWriter.write( '\n' )
    #fileWriter.close()

    true_boxes_max = nms_max(boxes_total, 0.2)
    #draw_boxes( true_boxes_max, imgs, im, info1[0]+'true_boxes_max.jpg')
    
    #true_boxes_avg = nms_average(boxes_total, 0.2)
    #draw_boxes( true_boxes_avg, imgs, im, info1[0]+'true_boxes_avg,jpg')

    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.05)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_1.jpg')
  
    #true_boxes_avg_max = nms_max(np.array(true_boxes_avg), 0.07)
    #draw_boxes( true_boxes_avg_max, imgs, im, info1[0]+'true_boxes_avg_max.jpg')
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.07)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_2.jpg')

    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.1)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_3.jpg')

    true_boxes_max = nms_max(boxes_total, 0.3)
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.05)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_4.jpg')
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.07)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_5.jpg')
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.1)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_6.jpg')

    true_boxes_max = nms_max(boxes_total, 0.4)
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.05)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_7.jpg')
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.07)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_8.jpg')
    true_boxes_max_avg = nms_average(np.array(true_boxes_max), 0.1)
    draw_boxes( true_boxes_max_avg, imgs, im, info1[0]+'_9.jpg')

    #===================
    #plt.savefig('heatmap/'+image_name.split('/')[-1])
    #在图像中画出检测到的人脸框

    plt.close()
    return out['prob'][0,map_idx]
    
    
if __name__ == "__main__":
    if not os.path.isfile(model_weight_fc):
        net_fc = convert_full_conv(model_define,model_weight,model_define_fc,model_weight_fc)
    else:
        net_fc = caffe.Net(model_define_fc, model_weight_fc, caffe.TEST)
    net_vf = caffe.Net(model_define, model_weight, caffe.TEST)

#logging module
    logging.basicConfig(level = logging.DEBUG,format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename='batch_detect.log', filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    logging.info('begin...')

    imgList = "/home/mjd/FaceDetection_CNN/face_rect_test.txt"
    imgFile = open(imgList)
    #first line is header infomation
    line = imgFile.readline()
    #the 1st line indicating image path and face position
    #for i in range(2):
    #    line = imgFile.readline()
    for i in range(10):
        line = imgFile.readline()
        #if not line: break
        line = line.strip()
        info = line.split( '\t' )
        filepath = '/home/mjd/FaceDetection_CNN/aflw/data/' + info[1]
        logging.info('testing ' + info[1])
        if not os.path.exists( filepath ):#the image file does not exist
            line = imgFile.readline()
            line = line.strip()
            logging.info( filepath + ' does not exist')
            continue
        fm = face_detection_image(net_fc,net_vf,filepath)
        plt.close('all')
        #break
    logging.info('All process done.\n')
