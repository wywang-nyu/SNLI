import tqdm
import torch
import torch.nn.functional as F
from models.rnn import RNN
from SNLI_DataLoader import SNLIDataset, snli_collate_func
import os
class rnn_trainer():
    
    def __init__(self, train_data, val_data, pre_trained_emb, args):
        
        self.device = torch.device(args['device'])
        
        #data
        self.train_data = train_data
        self.val_data = val_data
        self.batch_size = args['batch_size']
        
        #init model
        model_args = {'hidden_size': args['hidden_size'], 
                     'num_layers': args['num_layers'],
                     'num_classes': args['num_classes'],
                     'dropout': args['dropout'],
                     'device': self.device
                     }
        self.model = RNN(model_args, pre_trained_emb)
        
        #training-level parameter
        self.lr = args['learning_rate']
        if args['optim'] == 'adam':
            self.optim = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.criterion = torch.nn.CrossEntropyLoss()
        self.num_epochs = args['num_epochs']
        self.args = args
    def _load_data(self):
        train_dataset = SNLIDataset(self.train_data)
        self.train_loader = torch.utils.data.DataLoader(dataset=train_dataset,
                                                   batch_size=self.batch_size,
                                                   collate_fn=snli_collate_func,
                                                   shuffle=True)
        val_dataset = SNLIDataset(self.val_data)
        self.val_loader = torch.utils.data.DataLoader(dataset=val_dataset,
                                                   batch_size=self.batch_size,
                                                   collate_fn=snli_collate_func,
                                                   shuffle=True)

    def train_stage(self):
        train_loss = 0
        data_count = 0
        for data in self.train_loader:
            prem, prem_len, hyp, hyp_len, labels = [data[i].to(self.device) for i in range(len(data))]
            self.model.train()
            self.optim.zero_grad()
            # Forward pass
            outputs = self.model(prem, prem_len, hyp, hyp_len)
            loss = self.criterion(outputs, labels)

            # Backward and optimize
            loss.backward()
            self.optim.step()
            
            #document loss
            train_loss += loss.item()
            data_count += prem.size()[0]
            
        return train_loss/data_count
    def eval_stage(self):
        self._load_data()
        correct = 0
        total = 0
        self.model.eval()
        for data in self.val_loader:
            prem, prem_len, hyp, hyp_len, labels = [data[i].to(self.device) for i in range(len(data))]
            outputs = F.softmax(self.model(prem, prem_len, hyp, hyp_len), dim=1)
            predicted = outputs.max(1, keepdim=True)[1]

            total += labels.size(0)
            correct += predicted.eq(labels.view_as(predicted)).sum().item()
        return (100 * correct / total)

    def go(self):
        self._load_data()
        val_acc_list = []
        train_loss_list = []
        for epoch in tqdm.trange(self.num_epochs):
            train_loss = self.train_stage()
            train_loss_list.append(train_loss)
            val_acc = self.eval_stage()
            val_acc_list.append(val_acc)
        return train_loss_list, val_acc_list
    
    def save_model(self, model_dir, model_name):
        """
        save model
        @Args model_dir: directory for saving the model
        @Args model_name: name of the model 
        """
        fileloc = os.path.join(model_dir, model_name+'.pth')
            
        with open(fileloc, 'wb') as f:
            torch.save({'state_dict': self.model.state_dict(), 'config_dict': self.args}, f)
            
    def load_model(self, model_dir, model_name):
        fileloc = os.path.join(model_dir, model_name+'.pth')
        with open(fileloc, 'rb') as model_dict:
            checkpoint = torch.load(model_dict)
        
        
        self.model.load_state_dict(checkpoint['state_dict'])
