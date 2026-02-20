import sys
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import time

def check_environment():
    print("=== 环境检查 ===")
    print(f"Python 版本: {sys.version}")
    print(f"OpenCV 版本: {cv2.__version__}")
    print(f"NumPy 版本: {np.__version__}")
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"CUDA 是否可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA 版本: {torch.version.cuda}")
        print(f"当前设备: {torch.cuda.get_device_name(0)}")
    print("===============")

def test_yolo():
    # 环境检查
    check_environment()
    
    # 加载YOLO模型
    print("正在加载YOLO模型...")
    try:
        model = YOLO('yolov8n.pt')
        print("模型加载成功")
    except Exception as e:
        print(f"模型加载失败: {e}")
        return
    
    # 读取测试图片
    image_path = 'test.jpeg'
    print(f"正在读取图片: {image_path}")
    try:
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"无法读取图片: {image_path}")
            return
        print(f"图片尺寸: {frame.shape}")
    except Exception as e:
        print(f"读取图片时出错: {e}")
        return
    
    print("开始运行YOLO检测...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 运行YOLO检测
    try:
        results = model(frame, verbose=False)
        print("检测完成")
    except Exception as e:
        print(f"检测过程出错: {e}")
        return
    
    # 处理检测结果
    try:
        for result in results:
            # 获取检测框
            boxes = result.boxes.xyxy.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            cls = result.boxes.cls.cpu().numpy()
            
            print(f"检测到 {len(boxes)} 个物体")
            
            # 获取类别名称
            class_names = model.model.names

            # 绘制检测结果
            for box, conf, cl in zip(boxes, confs, cls):
                x1, y1, x2, y2 = box.astype(int)
                # 绘制边界框
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # 显示类别和置信度
                label = f"{class_names[int(cl)]} {conf:.2f}"
                cv2.putText(frame, label, (x1, y1 - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    except Exception as e:
        print(f"处理结果时出错: {e}")
        return
    
    # 计算处理时间
    process_time = time.time() - start_time
    print(f"处理时间: {process_time:.3f}秒")
    
    # 显示结果
    try:
        cv2.imshow('YOLOv8 Test', frame)
        print("按任意键退出...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except Exception as e:
        print(f"显示结果时出错: {e}")
    
    # 保存结果
    try:
        output_path = 'test_result.jpg'
        cv2.imwrite(output_path, frame)
        print(f"结果已保存到: {output_path}")
    except Exception as e:
        print(f"保存结果时出错: {e}")

if __name__ == "__main__":
    test_yolo() 