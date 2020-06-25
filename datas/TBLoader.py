import torch
import torch.utils.data as data
import random
import numpy as np
from scipy.ndimage import rotate
import os
import scipy.misc
from glob import glob
from scipy import io
import copyreg

# ignore skimage zoom warning
import warnings

warnings.filterwarnings("ignore", ".*output shape of zoom.*")


class TBDataset(data.Dataset):
    # TODO : infer implementated
    def __init__(self, img_root, channel, rotate_num=0, sampler=None, infer=False, transform=None, torch_type="float",
                 augmentation_rate=0.3):

        img_paths = glob(img_root + '/*.mat')
        if len(img_paths) == 0:
            raise ValueError("Check data path : %s" % (img_root))

        self.origin_image_len = len(img_paths)
        self.img_paths = img_paths
        # if transform is not None:
        #    self.img_paths += random.sample(img_paths, int(self.origin_image_len * augmentation_rate) )

        self.transform = [] if transform is None else transform
        self.torch_type = torch.float if torch_type == "float" else torch.half
        self.rotate_num=rotate_num

        self.channel = channel

    def __getitem__(self, idx):
        if self.channel == 1:
            return self._3D_image(idx)
        elif self.channel > 1:
            # return self._25D_image(idx)
            return self._2D_image(idx)
        else:
            raise ValueError("NSDataset data type must be 2d, 25d, 3d")

    def __len__(self):
        return len(self.img_paths)

    def _np2tensor(self, np):
        tmp = torch.from_numpy(np)
        return tmp.to(dtype=self.torch_type)

    # TODO : infer implementated
    def _3D_image(self, idx):
        img_path = self.img_paths[idx]
        data_pack = io.loadmat(img_path)
        # 2D ( 1 x H x W )
        input_np = data_pack['input']
        target_np = data_pack['target']

        # ToDo : Crop th
        x=192
        x_=x//2
        if(input_np.shape[1] > x):
            t=int(input_np.shape[1] / 2)
            input_np=input_np[t-x_:t+x_,t-x_:t+x_,:]
            target_np=target_np[t-x_:t+x_,t-x_:t+x_,:]
        t = int(input_np.shape[2] / 2)
        #input_np = input_np[:, :, t - 48:t + 48]
        #target_np = target_np[:, :, t - 48:t + 48]

        #input_np=input_np[::-1,::-1,:]
        input_np=rotate(input_np,90*self.rotate_num)

        # if idx >= self.origin_image_len:
        for t in self.transform:
            input_np, target_np = t(input_np, target_np)

        input_ = self._np2tensor(input_np[:, :, :].copy())
        target_ = self._np2tensor(target_np[:, :, :].copy())
        return input_[None], target_[None], os.path.basename(img_path)

    def _25D_image(self, idx):
        img_path = self.img_paths[idx]
        img = np.load(img_path)

        input_np = img[:, :448, :]
        target_np = img[:, 448:, 2:3]

        for t in self.transform:
            input_np, target_np = t([input_np, target_np])

        input_ = self._np2tensor(input_np).permute(2, 0, 1)
        target_ = self._np2tensor(target_np).permute(2, 0, 1)

        return input_, target_, os.path.basename(img_path)


def make_weights_for_balanced_classes(seg_dataset):
    count = [0, 0]  # No mask, mask
    for img, mask in seg_dataset:
        count[int((mask > 0).any())] += 1

    N = float(sum(count))
    weight_per_class = [N / c for c in count]

    weight = [0] * len(seg_dataset)
    for i, (img, mask) in enumerate(seg_dataset):
        weight[i] = weight_per_class[int((mask > 0).any())]

    return weight, count


def TBloader(image_path, batch_size,
                  transform=None, sampler='',
                  channel=1, torch_type="float", cpus=1, infer=False,
                  shuffle=True, drop_last=True, rotate_num=0):
    dataset = TBDataset(image_path, channel, rotate_num=rotate_num, infer=infer, transform=transform, torch_type=torch_type)


    if sampler == "weight":
        weights, img_num_per_class = make_weights_for_balanced_classes(dataset)
        print("Sampler Weights : ", weights)
        weights = torch.DoubleTensor(weights)
        img_num_undersampling = img_num_per_class[1] * 2
        print("UnderSample to ", img_num_undersampling, " from ", img_num_per_class)
        sampler = data.sampler.WeightedRandomSampler(weights, img_num_undersampling)
        return data.DataLoader(dataset, batch_size, sampler=sampler,
                               shuffle=False, num_workers=cpus, drop_last=drop_last)

    return data.DataLoader(dataset, batch_size, shuffle=shuffle, num_workers=cpus, drop_last=drop_last)


if __name__ == "__main__":
    # Test Data Loader
    f_path = "/home/Jinyeop/PyCharmProjects_JY/180818_3DcellSegmentation_JY_ver1/data/"
