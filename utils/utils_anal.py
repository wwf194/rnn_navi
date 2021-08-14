
import time
import os
import traceback
import pickle
import random
import math

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils import data
from torch.utils.data import DataLoader
from torch.autograd import Variable
from torch.optim.lr_scheduler import MultiStepLR,ReduceLROnPlateau

import torchvision
from torchvision.datasets import mnist
import torchvision.transforms as transforms

import pandas as pd
import numpy as np
import scipy
import seaborn as sns
import matplotlib as mpl
import matplotlib.pyplot as plt
import importlib
importlib.reload(mpl); importlib.reload(plt); importlib.reload(sns)

import cv2 as cv
from imageio import imsave

from utils_anal import *

from utils import *

def get_data_stat(data):
    return "mean=%.2e var=%.2e, min=%.2e, max=%.2e mid=%.2e"%(np.mean(data), np.var(data), np.min(data), np.max(data), np.median(data))

def get_log_data_1d(data):
    zero_index=[]
    count0=0
    count1=0
    count=data.shape[0]
    data_log=[None for _ in range(count)]
    for dat in data:
        if(dat>0.0):
            data_log[count1] = (math.log(dat, 10))
        elif(dat<0.0):
            print("%s is not a positive data"%(name))
            return False
        else:
            count0 += 1
            data_log[count1] = np.max(data)
            zero_index.append(count1)
        count1 += 1

    min_ = np.min(data_log)
    for index in zero_index:
        data_log[index] = min_
    data_log=np.array(data_log)
    note="non-zero rate: %.3f(%.1e/%.1e)"%((count-count0)/count, count-count0, count)
    return data_log, note

def visualize_weight(net, name="r", save_path="./"):
    ensure_dir(save_path)
    color_map = plt.cm.get_cmap('jet')
    w = net.get_weight(name, positive=True).detach().cpu().numpy()
    shape = w.shape
    #w, note = get_log_data_1d(w.reshape((shape[0] * shape[1])))
    #w = w.reshape((shape[0], shape[1]))
    #print(note)
    print(get_data_stat(w))
    w = ( w - np.min(w) ) / (np.max(w) - np.min(w))
    #w = w * 25
    #w = np.float32(w > 1.0) + np.float32(w<=1.0) * w
    print(get_data_stat(w))
    w = color_map(w)
    w = np.uint8(w * 255)
    print(w.shape)
    imsave(save_path + "%s visualization.png"%(name), w)    

def get_input_output(traj):
    if input_type in ["v_xy"]:
        #print(traj["hd_x"])
        #print(traj["delta_xy"])
        #print(traj["hd_x"] * traj["delta_xy"])
        #print((traj["hd_x"] * traj["delta_xy"]).shape)
        #print(traj["hd_x"].shape)
        #print(traj["delta_xy"].shape)
        #input()
        inputs = torch.from_numpy(np.stack((traj["hd_x"] * traj["delta_xy"], traj["hd_y"] * traj["delta_xy"]), axis=-1)).float() #(batch_size, sequence_length, (cos, sin, v))
        outputs = torch.from_numpy(np.stack((traj["target_x"], traj["target_y"]), axis=-1)).float() #(batch_size, sequence_length, (x, y))
    elif input_type in ["v_hd"]:
        inputs = torch.from_numpy(np.stack((traj["hd_x"], traj["hd_y"], traj["delta_xy"]), axis=-1)).float() #(batch_size, sequence_length, (cos, sin, v))
        outputs = torch.from_numpy(np.stack((traj["target_x"], traj["target_y"]), axis=-1)).float() #(batch_size, sequence_length, (x, y))
    init = torch.cat( [torch.from_numpy(traj["init_x"]), torch.from_numpy(traj["init_y"])], dim=1 ) #(batch_size, 2)
    return (inputs, init), outputs

def get_place_cells_activation(place_cells_0, x_resolution, y_resolution):
    pos = np.empty(shape=[x_resolution * y_resolution, 2], dtype=float) #coordinates

    for i in range(x_resolution):
        for j in range(y_resolution):
            pos[i * x_resolution + j][0], pos[i * x_resolution + j][1] = get_float_coords(i, j, box_width, box_height, x_resolution, y_resolution)

    pos  = torch.from_numpy(pos)
    pos = pos.to(device)
    pos = torch.unsqueeze(pos, 0) #(1, coordinate_num, (x, y))
    place_cells_act = place_cells_0.get_activation(pos) #(1, x_resolution * y_resolution, place_cells_num)
    return torch.squeeze(place_cells_act)

def plot_encoder_prediction(net=None, res=30, cmap='jet', exaggerate=False, save_path="./", save="img"):#(1, x_resolution * y_resolution, 2)
    if(net is None):
        net = load_net()
    
    x_resolution = res
    y_resolution = res

    if model_type in ["linear", "rnn"]:
        place_cells_0 = net.place_cells
        place_cells_act = get_place_cells_activation(place_cells_0, x_resolution, y_resolution).float() #(coordinate_num, place_cells_num)
        prediction = (1.0 - net.time_const) * torch.mm(place_cells_act, net.get_i_0_x()) + net.time_const * ( torch.mm(place_cells_act, net.get_i_0_r()) + net.b)
        if model_type=="linear":
            prediction = net.act_func(prediction)
        elif model_type=="rnn":
            prediction = net.N.act_func(prediction)
    elif model_type in ["lstm"]:
        pos = np.empty(shape=[x_resolution * y_resolution, 2], dtype=float) #coordinates
        for i in range(x_resolution):
            for j in range(y_resolution):
                pos[i * x_resolution + j][0], pos[i * x_resolution + j][1] = get_float_coords(i, j, box_width, box_height, x_resolution, y_resolution)
        pos = torch.from_numpy(pos)
        i_ = torch.zeros((pos.size(0), 1, net.dict["input_num"]), device=device)
        print(pos.size())
        output, prediction = net.forward( (i_ , pos) )
        print(output.size())
        print(prediction.size())
        prediction = torch.squeeze(prediction)
    images = []
    for k in range(net.dict["N_num"]):
        act = prediction[:, k].view(x_resolution, y_resolution)
        '''
        act = np.ones([x_resolution, y_resolution])
        for i in range(x_resolution):
            for j in range(y_resolution):
                act[i][j] = prediction[i * x_resolution + j, k].item()
        '''
        act = torch.unsqueeze( act.detach().cpu(), 0 )
        images.append(act)
    
    acts = torch.cat(images, dim=0).numpy()
    if save=="img":
        fig = plot_ratemaps(acts, n_plots=acts.shape[0], cmap=cmap, exaggerate=exaggerate, width=16)
        imsave(save_dir + "predicted_gc_pattern_" + cmap + ".png", fig)
    else:
        return acts

def load_net(epoch=None): #load lastest model saved in save_dir_stat
    if(epoch is None):
        net_path = get_last_model(model_prefix="Navi_epoch_", base_dir="./", is_dir=True)
    else:
        net_path=save_dir_stat + "Navi_epoch_%d/"%(epoch)

    print("loading net from " + net_path)

    f=open(net_path+"state_dict.pth","rb")
    if model_type=="rnn":
        net=RNN_Navi(load=True, f=f)
    elif model_type=="linear":
        net=Linear_Navi(load=True, f=f)
    elif model_type=="lstm":
        net=LSTM_Navi(load=True, f=f)
    else:
        print("unknown model type:"+str(model_type))
        input()
    f.close()
    net = net.to(device)
    return net


def compare_traj(net=None, save_path="./", x_resolution=400, save_name="undefined traj plot", sequence_length_0=None, arena_index=0, plot_num=1, outputs=None, outputs_0=None):
    ensure_path(save_path)
    if sequence_length_0 is None:
        sequence_length_0 = sequence_length #use sequence length in param_config.py

    if outputs is None or outputs_0 is None:
        traj = global_trajectory_generator.generate_trajectory(batch_size=batch_size, sequence_length=sequence_length_0, random_init=random_init_, arena_index=arena_index)
        inputs, outputs_0 = get_input_output(traj)
        #inputs = inputs.to(device)
        outputs_0 = outputs_0.to(device)
        if net is None:
            net=load_net()
        outputs, act = net.forward(inputs)

    y_resolution = int(x_resolution * box_height / box_width)
    img = np.zeros((x_resolution, y_resolution, 3), np.uint8)

    img[:,:,:]=(255, 255, 255) #background color = white

    for i in range(plot_num):
        traj = outputs[i]
        traj_0  = outputs_0[i]
        #print(traj_0[0])
        #input()
        #trajectory: (sequence_length_0, (x,y))
        if(isinstance(traj, torch.Tensor)):
            traj = traj.detach().cpu().numpy()
        
        line_color = (255, 0, 0) #(b, g, r)
        line_width = 2
        line_type = 4
        #plot ground truth trajectory
        plot_polyline(traj_0, img, sequence_length_0, box_width, box_height, x_resolution, y_resolution, line_color, line_width, line_type)

        line_color = (0, 255, 0) #(b, g, r)
        plot_polyline(traj, img, sequence_length_0, box_width, box_height, x_resolution, y_resolution, line_color, line_width, line_type)

        plot_arena(global_trajectory_generator.arena_dicts[arena_index], img, global_trajectory_generator.cache["box_width"], global_trajectory_generator.cache["box_height"], 
            x_resolution, y_resolution, line_width=1)

    cv.imwrite(save_path +  save_name + ".jpg", img)

def plot_init_positions(trajectory_generator=None, x_resolution=400, plot_num=50, save_path="./", save_name="init_positions_plot"):
    ensure_dir(save_path)
    if trajectory_generator is None:
        path = global_trajectory_generator
    else:
        path = trajectory_generator
    y_resolution = int(x_resolution * box_height / box_width)
    for num in range(path.arena_num):
        arena_dict = path.arena_dicts[num]
        arena_type = arena_dict["type"]
        traj = path.generate_trajectory(batch_size=plot_num, sequence_length=sequence_length, random_init=random_init_)
        inputs, outputs_0 = get_input_output(traj)

        img = np.zeros((x_resolution, y_resolution, 3), np.uint8)
        img[:,:,:] = (255, 255, 255) #background color: white
        plot_arena(arena_dict, img, path.cache["box_width"], path.cache["box_height"], x_resolution, y_resolution, line_width=3)
        point_size = 2
        point_color = (0, 0, 0) # BGR
        thickness = 4 # 可以为 0 、4、8
        for i in range(plot_num):
            #print("plot_num:%d"%i)
            init_posi = get_int_coords(outputs_0[i, 0, 0], outputs_0[i, 0, 1], box_width, box_height, x_resolution, y_resolution)
            cv.circle(img, init_posi, point_size, point_color, thickness)
        if arena_dict.get("points") is not None: #polygonal arena_type
            cv.imwrite(save_dir +  "%s(%s-%d).jpg"%(save_name, str(arena_type), arena_dict["points"].shape[0]), img)
        else:
            cv.imwrite(save_dir +  "%s(%s).jpg"%(save_name, str(arena_type)), img)

def plot_traj(trajectory_generator=None, save_path="./", res=400, save_name="undefined traj plot", plot_num=10): # res: resolution of longest dimension.
    ensure_path(save_path)
    
    if trajectory_generator is None:
        path = global_trajectory_generator
    else:
        path = trajectory_generator
    for num in range(path.arena_num):
        arena_dict = path.arena_dicts[num]
        arena_type = arena_dict["type"]
        
        traj = path.generate_trajectory(batch_size=plot_num, sequence_length=sequence_length, random_init=random_init_, arena_index=num)

        inputs, outputs_0 = get_input_output(traj)
        #inputs = inputs.to(device)
        outputs_0 = outputs_0.to(device)

        res_y = int(res_x * box_height / box_width)
        img = np.zeros((res_x, res_y, 3), np.uint8)
        img[:,:,:] = (255, 255, 255) #background color: white
        
        plot_arena(arena_dict, img, path.cache["box_width"], path.cache["box_height"], x_resolution, y_resolution, line_width=3)

        sample_num = outputs_0.size(1) #sequence_length
        line_color = (255, 0, 0) #(b, g, r)
        line_width = 2
        line_type = 4
        for i in range(plot_num):
            traj_0  = outputs_0[i]
            for i in range(sample_num-1):
                startPoint = get_int_coords(traj_0[i][0], traj_0[i][1], box_width, box_height, x_resolution, y_resolution)
                endPoint = get_int_coords(traj_0[i+1][0], traj_0[i+1][1], box_width, box_height, x_resolution, y_resolution)
                cv.line(img, startPoint, endPoint, line_color, line_width, line_type)
        if arena_dict.get("points") is not None:
            cv.imwrite(save_path +  "%s(%s-%d).jpg"%(save_name, str(arena_type), arena_dict["points"].shape[0]), img)
        else:
            cv.imwrite(save_path +  "%s(%s).jpg"%(save_name, str(arena_type)), img)

def print_notes(notes, y_line, y_interv):
    if(notes!=""):
        if(isinstance(notes, str)):
            plt.annotate(notes, xy=(0.02, y_line), xycoords='axes fraction')
            y_line-=y_interv
        elif(isinstance(notes, list)):
            for note in notes:
                plt.annotate(notes, xy=(0.02, y_line), xycoords='axes fraction')
                y_line-=y_interv
        else:
            print("invalid notes type")

def plot_dist(data, logger, name="undefined", ran=[], save_path="./", bins=100, kde=False, hist=True, notes="", redo=False, rug_max=False, stat=True, cumulative=False):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    if not isinstance(data, np.ndarray):
        data=np.array(data)
    data=data.flatten()
    data = np.sort(data)
    stat_data="mean=%.4f var=%.4f, min=%.4f, max=%.4f mid=%.4f"%(np.mean(data), np.var(data), np.min(data), np.max(data), np.median(data))
    
    num_max=100000
    if data.shape[0]>num_max:
        print("data is too large. sample %d elements.")
        data=np.array(random.sample(data.tolist(), num_max))
    logger.write(stat_data)
    img_dir={}
    
    y_interv = 0.05
    y_line=0.95
    #hist_plot

    if hist:
        sig=True
        sig_check=False
        while sig:
            try:
                title=name+" distribution"
                if(cumulative==True):
                    title+="(cumu)"
                hist_dir = save_dir + title +".jpg"
                img_dir["hist"]=hist_dir
                if(redo==False and os.path.exists(hist_dir)):
                    print("image already exists.")
                else:
                    plt.figure()
                    if(ran!=[]):
                        plt.xlim(ran[0],ran[1])
                    else:
                        set_lim(data, None, plt)
                    #sns.distplot(data, bins=bins, color='b',kde=False)
                    #method="sns"
                    plt.hist(data, bins=bins,color="b",density=True, cumulative=cumulative)
                    method="hist"

                    plt.title(title, fontsize=large_fontsize)
                    if(stat==True):
                        plt.annotate(stat_data, xy=(0.02, y_line), xycoords='axes fraction')
                        y_line-=y_interv
                    print_notes(notes, y_line, y_interv)
                    plt.savefig(hist_dir)
                    plt.close()
                sig=False
            except Exception:
                if(sig_check==True):
                    raise Exception("exception in plot dist.")
                data, note = check_array_1d(data, logger)
                if(isinstance(notes, str)):
                    notes = [notes, note]
                elif(isinstance(notes, list)):
                    notes = notes + [note]
                sig_check=True
    try: #kde_plot
        y_line=0.95
        if kde:
            title=name+" dist(kde)"
            if(cumulative==True):
                title+="(cumu)"
            kde_dir=save_dir+title+".jpg"
            img_dir["kde"]=kde_dir
            if(redo==False and os.path.exists(kde_dir)):
                print("image already exists.")
            else:
                plt.figure()
                if(ran!=[]):
                    plt.xlim(ran[0],ran[1])
                else:
                    set_lim(data, None, plt)
                sns.kdeplot(data, shade=True, color='b', cumulative=cumulative)
                if rug_max:
                    sns.rugplot(data[(data.shape[0]-data.shape[0]//500):-1], height=0.2, color='r')
                plt.title(title, fontsize=large_fontsize)
                if stat:
                    plt.annotate(stat_data, xy=(0.02, y_line), xycoords='axes fraction')
                    y_line-=0.05
                print_notes(notes, y_line, y_interv)
                plt.savefig(kde_dir)
                plt.close()
    except Exception:
        print("exception in kde plot %s"%(kde_dir))
    return img_dir

def plot_log_dist(data, logger, name="undefined", save_path="./", cumulative=False, hist=True, kde=False, bins=60):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    if(isinstance(data, torch.Tensor)):
        data = data.numpy()
    data=data.flatten()
    data_log=[]
    count_0=0
    count=data.shape[0]
    for dat in data:
        if(dat>0.0):
            data_log.append(math.log(dat, 10))
        elif(dat<0.0):
            print("%s is not a positive data"%(name))
            return False
        else:
            count_0+=1
    data_log=np.array(data_log)
    note="non-zero rate: %.4f(%d/%d)"%((count-count_0)/count, count-count_0, count)
    if count_0==count:
        logger.write("%s is all-zero."%(name))
        return True
    plot_dist(data=data_log, logger=logger, name=name+"(log)", save_dir=save_dir, notes=note, cumulative=cumulative, hist=hist, kde=kde, bins=bins)
    return True

def set_corr_method(method):
    if(isinstance(method, str)):
        if(method=="all"):
            method=["pearson", "kendall", "spearman"]
        else:
            method=[method]
        return method
    elif(isinstance(method, list)):
        return method
    else:
        print("invalid method type")
        return None

def set_lim(x, y=None, plt=""):
    if(y is None):
        x_min = np.min(x)
        x_max = np.max(x)
        xlim=[1.1*x_min-0.1*x_max, -0.1*x_min+1.1*x_max]
        plt.xlim(xlim[0], xlim[1])
        return xlim
    else:
        x_min = np.min(x)
        x_max = np.max(x)
        y_min = np.min(y)
        y_max = np.max(y)

        xlim=[1.1*x_min-0.1*x_max, -0.1*x_min+1.1*x_max]
        ylim=[1.1*y_min-0.1*y_max, -0.1*y_min+1.1*y_max]
        try:
            plt.xlim(xlim[0], xlim[1])
        except Exception:
            print(Exception)
            print("exception when setting xlim.")
            #print("input anything to continue")
            #input()
        try:
            plt.ylim(ylim[0], ylim[1])
        except Exception:
            print(Exception)
            print("exception when setting ylim.")
            #print("input anything to continue")
            #input()

        return xlim, ylim

def ensure_path(path):
    if not os.path.exists(path):
        os.makedirs(path)

def combine_name(name):
    return name[0] + " - " + name[1]

def get_corr_note(corr):
    note="corr"
    if(corr.get("pearson") is not None):
        note+=" pearson:%.4f"%(corr["pearson"])
    if(corr.get("kendall") is not None):
        note+=" kendall:%.4f"%(corr["kendall"])
    if(corr.get("spearman") is not None):
        note+=" spearman:%.4f"%(corr["spearman"])
    return note

def check_array_2d(data, logger):
    x_num = data.shape[0]
    y_num = data.shape[1]
    count=0
    for i in range(x_num):
        for j in range(y_num):
            if(np.isnan(data[i][j]) == True):
                print("data(%d,%d) is NaN."%(i,j), end=' ')
                data[i][j]=0.0
                count+=1
            elif(np.isinf(data[i][j]) == True):
                print("data(%d,%d) is Inf."%(i,j), end=' ')
                data[i][j]=0.0
                count+=1

    note = "%.4f(%d/%d) elements in data in NaN or Inf."%(count/(x_num*y_num), count, x_num*y_num)
    logger.write(note)
    return data, note

def check_array_1d(data, logger):
    x_num = data.shape[0]
    count=0
    for i in range(x_num):
        if(np.isnan(data[i]) == True):
            print("data(%d) is NaN."%(i), end=' ')
            data[i]=0.0
            count+=1
        elif(np.isinf(data[i]) == True):
            print("data(%d) is Inf."%(i), end=' ')
            data[i]=0.0
            count+=1
    note = "%.4f(%d/%d) elements in data in NaN or Inf."%(count/(x_num), count, x_num)
    logger.write(note)
    return data, note

def get_corr(x, y, method="all", save=False, name="undefined", save_path="./"):
    corr={}
    method=set_corr_method(method)

    for m in method:
        corr[m]=pd.Series(x).corr(pd.Series(y), method=m)

    if(len(method)==1):
        corr = corr[method[0]]
    if save:
        f=open(save_dir + name, "wb")
        pickle.dump(corr, f)
        f.close()
    return corr

import imageio
def create_gif(image_list, gif_name, duration = 1.0):
    '''
    :param image_list: 这个列表用于存放生成动图的图片
    :param gif_name: 字符串，所生成gif文件名，带.gif后缀
    :param duration: 图像间隔时间, 单位s
    :return:
    '''
    frames = []
    for image_name in image_list:
        frames.append(imageio.imread(image_name))

    imageio.mimsave(gif_name, frames, 'GIF', duration=duration)
    return



def convert_to_colormap(im, cmap):
    im = cmap(im)
    im = np.uint8(im * 255)
    return im

def to_list(object):
    if(isinstance(object, list)):
        return object
    else:
        return [object]

def rgb(im, cmap='jet', smooth=True, exaggerate=False, arena_index=0, mask=None):
    cmap = plt.cm.get_cmap(cmap)
    np.seterr(invalid='ignore')  # ignore divide by zero err
    if exaggerate:
        im = (im - np.min(im)) / (0.5 * (np.max(im) - np.min(im))) - 0.5
        for i in range(im.shape[0]):
            for j in range(im.shape[1]):
                if(im[i][j] > 1.0):
                    im[i][j] = 1.0
                elif(im[i][j] < 0.0):
                    im[i][j] = 0.0
    else:
        im = (im - np.min(im)) / (np.max(im) - np.min(im))
    if smooth:
        im = cv.GaussianBlur(im, (3,3), sigmaX=1, sigmaY=0)
    im = cmap(im)

    im = np.uint8(im * 255)

    arena_dict = global_trajectory_generator.arena_dicts[arena_index]
    if mask is not None:
        im = im * mask[:, :, np.newaxis] #braodcast to color channel

    #plot_arena(global_trajectory_generator.arena_dicts[arena_index], im, path.cache["box_width"], path.cache["box_height"], im.shape[0], im.shape[1], line_width=1)
    
    #print("im.shape: " + str(im.shape))
    return im

def plot_ratemaps(activations, n_plots, cmap='jet', smooth=True, width=16, exaggerate=False, arena_index=0, masks=None):
    cmap = to_list(cmap)
    rm_fig = {}
    for cmap_ in cmap:
        images = []
        count = 0
        if masks is None:
            for im in activations[:n_plots]:
                images.append( rgb(im, cmap_, smooth, exaggerate, arena_index, mask=None) )
                count += 1
        else:
            for im in activations[:n_plots]:
                images.append( rgb(im, cmap_, smooth, exaggerate, arena_index, mask=masks[count]) )
                count += 1
        rm_fig[cmap_] = (concat_images_in_rows(images, n_plots//width, activations.shape[-1]))
    if len(cmap)==1:
        rm_fig = rm_fig[cmap[0]]
    return rm_fig
'''
def compute_ratemaps(net, res=100, random_init=False, arena_index=0):
    # Compute spatial firing fields
    if(model_type=="linear"):
        return plot_encoder_prediction(save="return")

    #res: resolution
    #Ng: Number of grid cells.
    N_num = net.dict["N_num"]

    #if not np.any(idxs):
    #    idxs = np.arange(Ng)
    #idxs = idxs[:Ng]

    #g = np.zeros([n_avg, batch_size * sample_num, Ng])
    #positions = np.zeros([n_avg, batch_size * sample_num, 2])

    activations = np.zeros([N_num, res, res])
    counts  = np.zeros([res, res])

    batch_num_0 = 100 * 200 * 200 // (batch_size * sequence_length)

    path = global_trajectory_generator
    for index in range(batch_num_0):
        with torch.no_grad():
            net.eval()
            count = 0
            loss_total = 0.0
            traj = path.generate_trajectory(batch_size=batch_size, sequence_length=sequence_length, random_init=random_init, arena_index=arena_index)
            inputs, outputs_0 = get_input_output(traj)
            #print("inputs:"+str(list(inputs.size())))
            #print("outputs_0:"+str(list(outputs_0.size())))
            #inputs=inputs.to(device)
            outputs_0 = outputs_0.to(device)
            outputs, act = net.forward(inputs) #act:(timestep, batch_size, N_num)
            #print("act shape:" + str(len(act)) + " " + str(len(act[0])) + str(list(act[0][0].size())))

            x_positions = traj["target_x"] #(batch_size, time_step)
            y_positions = traj["target_y"]

            act = list(map(lambda x:x.detach().cpu(), act))

        #inputs, pos_batch, _ = trajectory_generator.get_test_batch()
        #g_batch = model.g(inputs)
        
        #pos_batch = np.reshape(pos_batch, [-1, 2])
        #g_batch = np.reshape(tf.gather(g_batch, idxs, axis=-1), (-1, Ng))
        
        #g[index] = g_batch
        #positions[index] = pos_batch

        x_batch = (x_positions + box_width/2) / (box_width) * res
        y_batch = (y_positions + box_height/2) / (box_height) * res

        for i in range(batch_size): #batch_index
            for j in range(sequence_length): #timestep
                x = x_batch[i, j]
                y = y_batch[i, j]
                #for k in range(N_num): #N_index
                if x >=0 and x <= res and y >=0 and y <= res:
                    counts[int(x), int(y)] += 1
                    activations[:, int(x), int(y)] += act[i][j].numpy()

    for x in range(res):
        for y in range(res):
            if counts[x, y] > 0:
                activations[:, x, y] /= counts[x, y]

    # # scipy binned_statistic_2d is slightly slower
    # activations = scipy.stats.binned_statistic_2d(pos[:,0], pos[:,1], g.T, bins=res)[0]
    rate_map = activations.reshape(N_num, -1)
    

    if use_masks:
        masks = np.uint8(activations!=0.0)
    else:
        masks = None
    return activations, masks
'''
def save_ratemaps(net, res=30, save_path="./", exaggerate=False, cmap='jet', random_init=False):
    ensure_dir(save_path)
    activations = compute_ratemaps(net, res=res, random_init=random_init)
    rm_fig = plot_ratemaps(activations, n_plots=len(activations), exaggerate=exaggerate, cmap=cmap, width=16)
    count = 0
    for fig in rm_fig:
        imsave(save_path + "/" + "heatmap_" + cmap[count] + ".png", rm_fig)
        count += 1

def save_autocorr(sess, model, save_name, trajectory_generator, step, flags):
    starts = [0.2] * 10
    ends = np.linspace(0.4, 1.0, num=10)
    coord_range=((-1.1, 1.1), (-1.1, 1.1))
    masks_parameters = zip(starts, ends.tolist())
    latest_epoch_scorer = scores.GridScorer(20, coord_range, masks_parameters)
    
    res = dict()
    index_size = 100
    for _ in range(index_size):
      feed_dict = trajectory_generator.feed_dict(flags.box_width, flags.box_height)
      mb_res = sess.run({
          'pos_xy': model.target_pos,
          'bottleneck': model.g,
      }, feed_dict=feed_dict)
      res = utils.concat_dict(res, mb_res)
        
    filename = save_name + '/autocorrs_' + str(step) + '.pdf'
    imdir = flags.save_path + '/'
    out = utils.get_scores_and_plot(
                latest_epoch_scorer, res['pos_xy'], res['bottleneck'],
                imdir, filename)

def get_data_stat(data):
    return "mean=%.2e var=%.2e, min=%.2e, max=%.2e mid=%.2e"%(np.mean(data), np.var(data), np.min(data), np.max(data), np.median(data))