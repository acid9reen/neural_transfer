from __future__ import print_function

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from PIL import Image
import matplotlib.pyplot as plt

import torchvision.transforms as transforms
import torchvision.models as models

import copy


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMAGE_SIZE = 512 if torch.cuda.is_available() else 128


def image_loader_init(loader):
    loader = loader

    def image_loader(image_name):
        image = Image.open(image_name)
        image = loader(image).unsqueeze(0)

        return image.to(DEVICE, torch.float)

    return image_loader


def show_image_init(unloader):
    unloader = unloader

    def show_image(tensor, title=None):
        image = tensor.cpu().clone()
        image = image.squeeze(0)
        image = unloader(image)

        plt.imshow(image)
        if title:
            plt.title(title)

        plt.pause(1)

    return show_image


def main() -> None:
    loader = transforms.Compose([
        transforms.Resize(IMAGE_SIZE),
        transforms.ToTensor(),
    ])

    image_loader = image_loader_init(loader)
    style_image = image_loader("./images/picasso.jpg")
    content_image = image_loader("./images/dancing.jpg")

    assert style_image.size() == content_image.size(), \
        "we need to import style and content images of the same size"

    unloader = transforms.ToPILImage()
    plt.ion()

    show_image = show_image_init(unloader)

    plt.figure()
    show_image(style_image, title="Style image")

    plt.figure()
    show_image(content_image, title="Content image")


if __name__ == "__main__":
    main()
