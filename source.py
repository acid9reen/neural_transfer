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
IMAGE_SIZE = 512 if DEVICE == "cuda" else 128


class ContentLoss(nn.Module):
    def __init__(self, target):
        super().__init__()
        self.target = target.detach()

    def forward(self, input):
        self.loss = F.mse_loss(input, self.target)
        return input


def gram_matrix(input):
    a, b, c, d = input.size()
    features = input.view(a * b, c * d)

    G = torch.mm(features, features.t())

    return G.div(a * b * c * d)


class StyleLoss(nn.Module):
    def __init__(self, target_feature):
        super().__init__()
        self.target = gram_matrix(target_feature).detach()

    def forward(self, input):
        G = gram_matrix(input)
        self.loss = F.mse_loss(G, self.target)

        return input


def image_loader_init(loader):
    def image_loader(image_name):
        image = Image.open(image_name)
        image = loader(image).unsqueeze(0)

        return image.to(DEVICE, torch.float)

    return image_loader


def show_image_init(unloader):
    def show_image(tensor, title=None):
        image = tensor.cpu().clone()
        image = image.squeeze(0)
        image = unloader(image)

        plt.imshow(image)
        if title:
            plt.title(title)

        plt.savefig(f"{title}.png", bbox_inches='tight', pad_inches=0)
        plt.pause(1)

    return show_image


class Normalization(nn.Module):
    def __init__(self, mean, std):
        super().__init__()

        self.mean = torch.tensor(mean).view(-1, 1, 1)
        self.std = torch.tensor(std).view(-1, 1, 1)

    def forward(self, img):
        return (img - self.mean) / self.std




def get_style_model_and_losses(cnn, normalization_mean, normalization_std,
                               style_img, content_img,
                               content_layers=None,
                               style_layers=None):
    content_layers_default = ['conv_4']
    style_layers_default = ['conv_1', 'conv_2', 'conv_3', 'conv_4', 'conv_5']
    content_layers = content_layers_default if (content_layers is None) else content_layers
    style_layers = style_layers_default if (style_layers is None) else style_layers
    cnn = copy.deepcopy(cnn)

    # normalization module
    normalization = Normalization(normalization_mean, normalization_std).to(DEVICE)

    # just in order to have an iterable access to or list of content/syle
    # losses
    content_losses = []
    style_losses = []

    # assuming that cnn is a nn.Sequential, so we make a new nn.Sequential
    # to put in modules that are supposed to be activated sequentially
    model = nn.Sequential(normalization)

    i = 0  # increment every time we see a conv
    for layer in cnn.children():
        if isinstance(layer, nn.Conv2d):
            i += 1
            name = 'conv_{}'.format(i)
        elif isinstance(layer, nn.ReLU):
            name = 'relu_{}'.format(i)
            # The in-place version doesn't play very nicely with the ContentLoss
            # and StyleLoss we insert below. So we replace with out-of-place
            # ones here.
            layer = nn.ReLU(inplace=False)
        elif isinstance(layer, nn.MaxPool2d):
            name = 'pool_{}'.format(i)
        elif isinstance(layer, nn.BatchNorm2d):
            name = 'bn_{}'.format(i)
        else:
            raise RuntimeError('Unrecognized layer: {}'.format(layer.__class__.__name__))

        model.add_module(name, layer)

        if name in content_layers:
            # add content loss:
            target = model(content_img).detach()
            content_loss = ContentLoss(target)
            model.add_module("content_loss_{}".format(i), content_loss)
            content_losses.append(content_loss)

        if name in style_layers:
            # add style loss:
            target_feature = model(style_img).detach()
            style_loss = StyleLoss(target_feature)
            model.add_module("style_loss_{}".format(i), style_loss)
            style_losses.append(style_loss)

    # now we trim off the layers after the last content and style losses
    for i in range(len(model) - 1, -1, -1):
        if isinstance(model[i], ContentLoss) or isinstance(model[i], StyleLoss):
            break

    model = model[:(i + 1)]

    return model, style_losses, content_losses


def get_input_optimizer(input_img):
    optimizer = optim.LBFGS([input_img.requires_grad_()])

    return optimizer


def run_style_transfer(
    cnn, normalization_mean, normalization_std,
    content_img, style_img, input_img, num_steps=300,
    style_weight=100000, content_weight=1
):
    print("Build the style transfer model...")
    model, style_losses, content_losses = get_style_model_and_losses(
        cnn, normalization_mean, normalization_std,
        style_img, content_img
    )
    optimizer = get_input_optimizer(input_img)

    print("Optimizing...")
    run = [0]
    while run[0] <= num_steps:
        def closure():
            input_img.data.clamp_(0, 1)

            optimizer.zero_grad()
            model(input_img)
            style_score = 0
            content_score = 0

            for sl in style_losses:
                style_score += sl.loss

            for cl in content_losses:
                content_score += cl.loss

            style_score *= style_weight
            content_score *= content_weight

            loss = style_score + content_score
            loss.backward()

            run[0] += 1

            if run[0] % 50 == 0:
                print(f"run {run}")
                print(f'Style Loss : {style_score.item():4f} Content Loss:'
                      f'{content_score.item():4f}')
                print()

            return style_score + content_score

        optimizer.step(closure)

    input_img.data.clamp_(0, 1)

    return input_img


def main() -> None:
    loader = transforms.Compose(
        [
            transforms.Resize(IMAGE_SIZE),
            transforms.ToTensor(),
        ]
    )

    image_loader = image_loader_init(loader)
    style_image = image_loader("./images/style.jpg")
    content_image = image_loader("./images/content.jpg")

    assert (
        style_image.size() == content_image.size()
    ), "we need to import style and content images of the same size"

    unloader = transforms.ToPILImage()

    show_image = show_image_init(unloader)

    cnn = models.vgg19(pretrained=True).features.to(DEVICE).eval()
    cnn_normalization_mean = torch.tensor([0.485, 0.456, 0.406]).to(DEVICE)
    cnn_normalization_std = torch.tensor([0.229, 0.224, 0.225]).to(DEVICE)

    input_img = content_image.clone()

    output = run_style_transfer(
        cnn, cnn_normalization_mean, cnn_normalization_std,
        content_image, style_image, input_img
    )

    plt.figure()
    show_image(output, title="out")


if __name__ == "__main__":
    main()

