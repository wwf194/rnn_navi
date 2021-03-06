import numpy as np
import random
import torch
import utils_torch

import matplotlib as mpl
from matplotlib import pyplot as plt

class Arena2D():
    def __init__(self, param=None):
        self.param = param
    def InitFromParam(self, param):
        self.param = param
    #@abc.abstractmethod
    def get_random_xy(self): # must be implemented by child class.
        return
    def GenerateRandomPointsInBoundaryBox(self, Num):
        param = self.param
        return np.stack([np.random.uniform(self.xMin, self.xMax, Num), np.random.uniform(self.y0, self.y1, Num)], axis=0) #[points_num, (x, y)]
    def GenerateRandomInternalPoints(self, Num=100, MinimumDistance2Border=None):
        if MinimumDistance2Border is None:
            MinimumDistance2Border = self.MinimumDistance2Border
        PointsNum = 0
        PointsList = []
        while(PointsNum < Num):
            Points = self.GenerateRandomPointsInBoundaryBox(int(2.2 * Num))            
            Points = np.delete(Points, self.isOutside(Points, MinimumDistance2Border=MinimumDistance2Border), axis=0)
            PointsList.append(Points)
            PointsNum += Points.shape[0]
            #print('total valid points:%d'%count)
        Points = np.concatenate(PointsList, axis=0)
        if PointsNum > Num:
            Points = np.delete(Points, random.sample(range(PointsNum), PointsNum - Num), axis=0)
        return Points
    def get_random_xy_max(self, num=100):
        xs = np.random.uniform(self.x0, self.x1, num) # x_0
        ys = np.random.uniform(self.y0, self.y1, num) # y_0
        xys = np.stack([xs,ys], axis=1) # np.stack will insert a dimension at designated axis. [num, 2]
        #print('get_random_xy_max: points shape:'+str(xys.shape))
        return xys
    def save(self, dir_):
        with open(dir_, 'wb') as f:
            net = self.to(torch.device('cpu'))
            torch.save(net.dict, f)
            net = self.to(self.device)
    def get_mask(self, res=None, res_x=None, res_y=None, points_grid=None):
        #print('res_x: %d res_y: %d'%(res_x, res_y))
        if res is not None:
            res_x, res_y = get_res_xy(res, self.width, self.height)
        if points_grid is not None:
            if points_grid.shape[0] != res_x * res_y:
                raise Exception('Arena.get_mask: points_grid shape must be consistent with res_x, res_y.')
        else:
            points_grid_int = np.empty(shape=[res_x, res_y, 2], dtype=np.int) # coord
            for i in range(res_x):
                points_grid_int[i, :, 1] = i # y_index
            for i in range(res_y):
                points_grid_int[:, i, 0] = i # x_index
            points_grid = get_float_coords_np( points_grid_int.reshape(res_x * res_y, 2), self.xy_range, res_x, res_y ) # [res_x * res_y, 2]
        arena_mask = np.ones((res_x, res_y)).astype(np.bool)
        #print('res_x: %d res_y: %d'%(res_x, res_y))
        #print(points_grid.shape)
        points_out_of_region = self.out_of_region(points_grid, thres=0.0)
        if points_out_of_region.shape[0] > 0:
            print(points_out_of_region)
            print(points_out_of_region.shape)
            points_out_of_region = np.array([points_out_of_region//res_x, points_out_of_region%res_x], dtype=np.int)
            print(points_out_of_region)
            print(points_out_of_region.shape)           
            points_out_of_region = points_out_of_region.transpose((1,0))
            
            for i in range(points_out_of_region.shape[0]):
                arena_mask[points_out_of_region[i,0], points_out_of_region[i,1]] = 0.0        
            #arena_mask[points_out_of_region] = 0.0 does not work.
        return arena_mask
    def PlotRandomInternalPoints(self, PointNum, SavePath):
        fig, ax = plt.subplots()
        Points = self.GenerateRandomInternalPoints(PointNum)
        self.PlotBoundary(ax)
        utils_torch.plot.PlotPointsNp(Points)
        plt.savefig(SavePath)


        