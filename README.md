# Deep Learning Model for Signal Data Prediction

## Instruction:
Run main.py to start the training and testing.<br />
Configuration of hyper parameters is also in main.py, including batch size, learning rate, etc.<br />
To configure, open main.py.<br />
If we want to train the dataset using fnn, set `model = "fnn"`
if we want to train the dataset using gru, set `model = "gru"`
'''

## Files:
- main.py: configuration and hyper tuning.<br />
- models.py: including all the architecture of all models.<br />
- utils.py: data loading using pytorch dataloader and dataset
- fnn.py: train and test setup of fnn model
- gru.py: train and test setup of gru model
