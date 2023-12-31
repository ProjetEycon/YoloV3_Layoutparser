from __future__ import division

from models import *
from utils.utils import *
from utils.datasets import *
from utils.parse_config import *

import os
import sys
import time
import datetime
import argparse

import torch
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision import transforms
from torch.autograd import Variable
import torch.optim as optim
import wandb

config = {
  "gpu":"gpu-4",
  "num_classes": 2,
  "batch_size":1,
  "image":2300
}

# Pass the config dictionary when you initialize W&B
run = wandb.init(project="yolo v3", config=config)
parser = argparse.ArgumentParser()
parser.add_argument("--epochs", type=int, default=20, help="number of epochs")
parser.add_argument("--image_folder", type=str, default="data/artifacts/images", help="path to dataset")
parser.add_argument("--batch_size", type=int, default=16, help="size of each image batch")
parser.add_argument("--model_config_path", type=str, default="config/yolov3.cfg", help="path to model config file")
parser.add_argument("--data_config_path", type=str, default="config/coco.data", help="path to data config file")
parser.add_argument("--weights_path", type=str, default="config/yolov3.weights", help="path to weights file")
parser.add_argument("--class_path", type=str, default="config/coco.names", help="path to class label file")
parser.add_argument("--conf_thres", type=float, default=0.8, help="object confidence threshold")
parser.add_argument("--nms_thres", type=float, default=0.4, help="iou thresshold for non-maximum suppression")
parser.add_argument("--n_cpu", type=int, default=0, help="number of cpu threads to use during batch generation")
parser.add_argument("--img_size", type=int, default=2300, help="size of each image dimension")
parser.add_argument("--checkpoint_interval", type=int, default=1, help="interval between saving model weights")
parser.add_argument("--checkpoint_dir", type=str, default="checkpoints", help="directory where model checkpoints are saved")
parser.add_argument("--use_cuda", type=bool, default=True, help="whether to use cuda if available")
opt = parser.parse_args()
print(opt)

cuda = torch.cuda.is_available() and opt.use_cuda
print(cuda)
os.makedirs("checkpoints", exist_ok=True)

classes = load_classes(opt.class_path)

# Get data configuration
data_config = parse_data_config(opt.data_config_path)
train_path = data_config["train"]

# Get hyper parameters
hyperparams = parse_model_config(opt.model_config_path)[0]
learning_rate = float(hyperparams["learning_rate"])
momentum = float(hyperparams["momentum"])
decay = float(hyperparams["decay"])
burn_in = int(hyperparams["burn_in"])

# Initiate model
print("init du model")
model = Darknet(opt.model_config_path)
print("model done")
print(model)
#model.load_weights(opt.weights_path)
model.apply(weights_init_normal)

if cuda:
    model = model.cuda()

model.train()
print("model.train")
# Get dataloader
dataset=ListDataset(train_path)
dataloader = torch.utils.data.DataLoader(
    ListDataset(train_path), batch_size=opt.batch_size, shuffle=False, num_workers=40
)
print(dataset[0])
print("loader done")
Tensor = torch.cuda.FloatTensor if cuda else torch.FloatTensor

optimizer = torch.optim.SGD(filter(lambda p: p.requires_grad, model.parameters()),lr=learning_rate)
print("debut du training")
from tqdm import tqdm
for epoch in range(opt.epochs):
    print('epoch:',epoch)
    batch_i=0
    optimizer.zero_grad()
    for  (_, imgs, targets) in tqdm(dataloader):
        #with torch.cuda.amp.autocast():
               
            imgs = Variable(imgs.type(Tensor))
            targets = Variable(targets.type(Tensor), requires_grad=False)
            loss = model(imgs, targets)
            loss.backward()
            if batch_i %8==0:
                print("i am doing the step")
                optimizer.step()
                optimizer.zero_grad()
                wandb.log({"totale":loss.item(),"x":float(model.losses["x"]),"y":float(model.losses["y"]),"pr":float(model.losses["precision"]),"recall":float(model.losses["recall"])})
                print(
            "[Epoch %d/%d, Batch %d/%d] [Losses: x %f, y %f, w %f, h %f, conf %f, cls %f, total %f, recall: %.5f, precision: %.5f]"
            % (
                epoch,
                opt.epochs,
                batch_i,
                len(dataloader),
                model.losses["x"],
                model.losses["y"],
                model.losses["w"],
                model.losses["h"],
                model.losses["conf"],
                model.losses["cls"],
                loss.item(),
                model.losses["recall"],
                model.losses["precision"],
            )
        
        )
            batch_i+=1
            model.seen += imgs.size(0)

    if epoch % opt.checkpoint_interval == 0:
        model.save_weights("%s/%d.weights" % (opt.checkpoint_dir, epoch))
