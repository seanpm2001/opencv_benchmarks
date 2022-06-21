#!/usr/bin/env python

"""qr.py
Usage example:
python qr.py -o out.yaml -p qrcodes/detection
-H, --help - show help
-o, --output - output file (default out.yaml)
-p, --path - input dataset path (default qrcodes/detection)
-a, --accuracy - input accuracy (default 47)
-alg, --algorithm - input alg (default opencv)
-m, --metric - input metric (default ~)
"""

import argparse
import glob
from enum import Enum

import numpy as np
import cv2 as cv


class DetectorQR:
    TypeDetector = Enum('TypeDetector', 'opencv opencv_wechat')
    detected_corners = None
    decoded_info = None
    detector = None
    type_detector = None

    def __init__(self, type_detector=TypeDetector.opencv, path_to_model="/home/alexander/all/pycharm/master/"):
        self.type_detector = type_detector
        if type_detector == self.TypeDetector.opencv:
            self.detector = cv.QRCodeDetector()
        elif type_detector == self.TypeDetector.opencv_wechat:
            self.detector = cv.wechat_qrcode_WeChatQRCode(path_to_model + "detect.prototxt",
                                                          path_to_model + "detect.caffemodel",
                                                          path_to_model + "sr.prototxt",
                                                          path_to_model + "sr.caffemodel")
        else:
            raise TypeError()

    def detect(self, image):
        if self.type_detector == self.TypeDetector.opencv:
            ret, corners = self.detector.detectMulti(image)
            self.detected_corners = corners
            return ret, corners
        elif self.TypeDetector.opencv_wechat:
            decoded_info, corners = self.detector.detectAndDecode(image)
            if len(decoded_info) == 0:
                return False, None
            corners = np.array(corners).reshape(-1, 4, 2)
            self.decoded_info = decoded_info
            self.detected_corners = corners
            return True, corners
        else:
            raise TypeError()

    def decode(self, image):
        if self.type_detector == self.TypeDetector.opencv:
            if self.detected_corners is None or self.detected_corners.size == 0:
                return 0, None, None
            r, decoded_info, straight_qrcode = self.detector.decodeMulti(image, self.detected_corners)
            self.decoded_info = decoded_info
            return r, decoded_info, straight_qrcode
        elif self.TypeDetector.opencv_wechat:
            if self.decoded_info is None or len(self.decoded_info) == 0:
                return 0, None, None
            return True, self.decoded_info, self.detected_corners
        else:
            raise TypeError()


def find_images_path(dir_path):
    images = glob.glob(dir_path + '/*.jpg')
    images += glob.glob(dir_path + '/*.png')
    return images


def get_corners(label_path):
    f = open(label_path, "r")
    corners = []
    for line in f.readlines():
        try:
            f_list = [float(i) for i in line.split(" ")]
            corners += f_list
        except ValueError as e:
            pass
    return np.array(corners).reshape(-1, 4, 2)


def get_distance(gold_corners, corners):
    return abs(np.amax(gold_corners - corners))


def get_distance_to_rotate_qr(gold_corner, corners, accuracy):
    corners = corners.reshape(-1, 4, 2)
    dist = 1e9
    for one_corners in corners:
        dist = get_distance(gold_corner, one_corners)
        if dist > accuracy:
            for i in range(0, 3):
                if dist > accuracy:
                    one_corners = np.roll(one_corners, 1, 0)
                    dist = min(dist, get_distance(gold_corner, one_corners))
                else:
                    return dist
        if dist > accuracy:
            one_corners = np.flip(one_corners, 0)
            dist = min(dist, get_distance(gold_corner, one_corners))
            for i in range(0, 3):
                if dist > accuracy:
                    one_corners = np.roll(one_corners, 1, 0)
                    dist = min(dist, get_distance(gold_corner, one_corners))
                else:
                    return dist
    return dist


def read_node():
    pass


def main():
    # parse command line options
    parser = argparse.ArgumentParser(description="bench QR code dataset", add_help=False)
    parser.add_argument("-H", "--help", help="show help", action="store_true", dest="show_help")
    parser.add_argument("-o", "--output", help="output file", default="out.svg", action="store", dest="output")
    parser.add_argument("-p", "--path", help="input dataset path", default="qrcodes/detection", action="store",
                        dest="path")
    parser.add_argument("-a", "--accuracy", help="input accuracy", default="20", action="store", dest="accuracy",
                        type=int)
    parser.add_argument("-alg", "--algorithm", help="QR detect algorithm", default="opencv", action="store",
                        dest="algorithm", type=str)

    args = parser.parse_args()
    show_help = args.show_help
    if show_help:
        parser.print_help()
        return
    output = args.output
    path = args.path
    accuracy = args.accuracy
    algorithm = args.algorithm

    list_dirs = glob.glob(path + "/*")
    fs = cv.FileStorage("out.yaml", cv.FILE_STORAGE_WRITE)
    fs.write("path", path)
    gl_qr_count = 0
    gl_qr_detect = 0
    gl_decode = 0

    qr = DetectorQR(DetectorQR.TypeDetector[algorithm], "/home/alexander/all/pycharm/master/")

    for dir in list_dirs:
        imgs_path = find_images_path(dir)
        qr_count = 0
        qr_detect = 0
        qr_decode = 0
        for img_path in imgs_path:
            label_path = img_path[:-3] + "txt"
            gold_corners = get_corners(label_path)
            qr_count += gold_corners.shape[0]

            image = cv.imread(img_path, cv.IMREAD_IGNORE_ORIENTATION)
            ret, corners = qr.detect(image)
            img_name = img_path[:-4].replace('\\', '_')
            img_name = img_name.replace('/', '_')
            fs.startWriteStruct(img_name, cv.FILE_NODE_MAP)
            fs.write("bool", int(ret))
            fs.write("gold_corners", gold_corners)
            fs.write("corners", corners)
            if ret is True:
                i = 0
                r, decoded_info, straight_qrcode = qr.decode(image)
                if len(decoded_info) > 0:
                    for info in decoded_info:
                        if info != "":
                            qr_decode += 1
                fs.write("decoded_info", decoded_info)
                for one_gold_corners in gold_corners:
                    dist = get_distance_to_rotate_qr(one_gold_corners, corners, accuracy)
                    fs.write("dist_to_gold_corner_" + str(i), dist)
                    if dist <= accuracy:
                        qr_detect += 1
                    i += 1
            # qr_detect += ret
            fs.endWriteStruct()

        # print(dir, qr_count, qr_detect, qr_detect / max(1, qr_count))
        print(dir, qr_detect / max(1, qr_count), qr_decode / max(1, qr_count), qr_count)
        gl_qr_count += qr_count
        gl_qr_detect += qr_detect
        gl_decode += qr_decode
    print(gl_qr_count)
    print(gl_qr_detect)
    print(gl_qr_detect / gl_qr_count)
    print("decode", gl_decode / gl_qr_count)


if __name__ == '__main__':
    main()
