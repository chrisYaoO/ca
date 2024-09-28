__all__ = ['cnn_train']

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import torch.nn.functional as F
import time
from tqdm import tqdm


class cnn(nn.Module):
    def __init__(self, scale=50):
        self.scale = scale
        super(cnn, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(128 * 4 * 4, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.pool(F.relu(self.conv3(x)))
        x = x.view(-1, 128 * 4 * 4)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

    def run(self):
        transform = transforms.Compose(
            [transforms.ToTensor(),
             transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])

        # 加载训练集和测试集
        trainset = torchvision.datasets.CIFAR10(root='./data', train=True, download=True, transform=transform)
        trainloader = DataLoader(trainset, batch_size=64, shuffle=True, num_workers=2)

        testset = torchvision.datasets.CIFAR10(root='./data', train=False, download=True, transform=transform)
        testloader = DataLoader(testset, batch_size=256, shuffle=False, num_workers=2)

        classes = ('plane', 'car', 'bird', 'cat', 'deer', 'dog', 'frog', 'horse', 'ship', 'truck')

        model = cnn(self.scale)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)

        num_epochs = 10
        start_time = time.perf_counter()
        print('start training')
        for epoch in range(num_epochs):
            running_loss = 0.0
            with tqdm(enumerate(trainloader, 0), total=len(trainloader),
                      desc=f'Epoch {epoch + 1}/{num_epochs}') as pbar:
                for i, data in pbar:
                    inputs, labels = data
                    optimizer.zero_grad()

                    outputs = model(inputs)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()

                    running_loss += loss.item()
                    if i % 100 == 99:  # 每100个批次打印一次损失
                        print(
                            f'Epoch [{epoch + 1}/{num_epochs}], Step [{i + 1}/{len(trainloader)}], Loss: {running_loss / 100:.4f}')
                        running_loss = 0.0

            elapsed_time = time.time() - start_time
            if elapsed_time > self.scale:  # 如果训练时间超过1分钟，提前停止
                print("Training stopped early due to time limit.")
                break

        print('Finished Training')
        torch.save(model.state_dict(), 'model.pth')
        print('model saved')


