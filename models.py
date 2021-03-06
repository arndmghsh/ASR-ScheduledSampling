import torch
import torch.nn as nn
import numpy as np
import torch.nn.functional as F
from torch import optim
import random

# for accesing files in the directory
import glob
import errno

# # Create a class Encoder, which inherits the properties and methods from the parent class nn.Module
# class EncoderLSTM(nn.Module):
#     def __init__(self):
#         super(EncoderLSTM, self).__init__()
#         self.input_size = 80   # given 20 x L acoustic inputs
#         self.hidden_size = 128
#         self.lstm = nn.LSTM(self.input_size, self.hidden_size, batch_first = True)
        
#     def forward(self, inp):
#         # input to LSTM = B x L x 20
#         output, hidden = self.lstm(inp)
#         # output, (h_n, c_n) = self.lstm(embedding, (h, c)) ----- (h,c) initialized to zero
#         # output size = B x L x 128
#         # (h,c) are from the last time step: both have size [1,B,128]
#         # return the last hidden output 1 x B x H
#         return (hidden[0][0,:,:],hidden[1][0,:,:])

class EncoderLSTM_multilayer(nn.Module):
    def __init__(self, n_layers, p_dropout):
        super(EncoderLSTM_multilayer, self).__init__()
        self.input_size = 80   # given 80 x L acoustic inputs
        self.hidden_size = 128
        self.n_layers = n_layers
        self.lstm = nn.LSTM(self.input_size, self.hidden_size, self.n_layers, dropout = p_dropout, batch_first = True)
        self.dropout = nn.Dropout(p_dropout)

    def forward(self, inp):
        # input to LSTM = B x L x 20
        input = self.dropout(inp)
        output, hidden = self.lstm(input)
        # output, (hidden_n, cell_n) = self.lstm(embedding, (h, c)) ----- (h,c) initialized to zero
        # output size = B x L x 128
        # (h,c) are from the last time step: both have size [n_layers, B,128] = n_layers x B x H
        return (hidden[0][:,:,:],hidden[1][:,:,:])        

# class DecoderLSTM(nn.Module):
#     def __init__(self, vocab_size):
#         super(DecoderLSTM, self).__init__()
#         self.vocab_size = vocab_size
#         self.embedding_size = 256
#         self.decoder_hidden_size = 128
#         self.embedding = nn.Embedding(vocab_size, self.embedding_size)        
#         # NOTE: Use LSTM Cell here instead if you want to control the hidden state at each time step.
#         self.lstm = nn.LSTMCell(self.embedding_size, self.decoder_hidden_size)
#         self.lin = nn.Linear(self.decoder_hidden_size, vocab_size)
       
#     def forward_step(self, word_embedding, hidden):
#         output, new_cell_state = self.lstm(word_embedding, hidden)
#         new_hidden = output
#         vocab_distrbtn = F.softmax(self.lin(output), dim=1)
#         return vocab_distrbtn, (new_hidden, new_cell_state)
        
#     def forward(self, inpt, encoder_hidden, mask_Y, beta):
#         t_max = inpt.shape[1]
#         batch_size = inpt.shape[0]

#         loss = 0
#         # SOS = 1
#         word = inpt[:,0]
#         word_embedding = self.embedding(word)

#         hidden = encoder_hidden
#         for t in range(t_max-1):
#             vocab_dist, hidden = self.forward_step(word_embedding, hidden)  # vocab_dist = B x V = 10 x 30
#             word = torch.argmax(vocab_dist, dim=1)   # word = B x 1
            
#             # DAgger policy = beta*oracle + (1-beta)*model
#             u = random.uniform(0, 1)
#             if u<=beta:
#                 # Teacher Forcing
#                 word_embedding = self.embedding(inpt[:,t+1])
#             else:
#                 # Model's output as next input
#                 word_embedding = self.embedding(word)
            
#             # Cross Entropy Loss
#             # ground truth B x 1 is the char at time step t+1 or t+1th column in B x L = 32 x L
#             true_label = inpt[:,t+1]            
#             # one hot encode the true label # B x 1 = 32 x 1 --> 32 x 30
#             onehot = torch.zeros((batch_size, self.vocab_size))
#             for i in range(batch_size):
#                 onehot[i][true_label[i]]=1
#             # Cross entropy loss: vocab_dist 32 x 30, onehot 32 x 30
#             NLL = (-1)*torch.log(vocab_dist)
#             ce_loss = torch.sum(NLL*onehot, dim=1)
#             loss += torch.sum(ce_loss*mask_Y[:,t]) 
#         # averaged loss over the entire batch (except padding)
#         return loss/torch.sum(mask_Y)

#     def forward_inference(self, encoder_output):
#         t_max = 80
#         prediction_int = []
#         # SOS = 1
#         char = torch.ones(1)
#         char = char.type(torch.LongTensor)
#         char_embedding = self.embedding(char)
#         # Feed in the encoder_hidden
#         hidden = encoder_output
#         for t in range(t_max-1):
#             vocab_dist, hidden = self.forward_step(char_embedding, hidden)  # vocab_dist = B x V = 10 x 30
#             char = torch.argmax(vocab_dist, dim=1) # word = B x 1
#             if char==2: 
#                 break
#             prediction_int.append(int(char))
#             # Model's output as next input
#             char_embedding = self.embedding(char)
#         return prediction_int


class DecoderLSTM_multilayer(nn.Module):
    def __init__(self, vocab_size, n_layers, p_dropout):
        super(DecoderLSTM_multilayer, self).__init__()
        self.vocab_size = vocab_size
        self.embedding_size = 256
        self.decoder_hidden_size = 128
        self.n_layers = n_layers
        self.embedding = nn.Embedding(vocab_size, self.embedding_size)        
        # NOTE: Use LSTM Cell here instead if you want to control the hidden state at each time step.
        # self.lstm = nn.LSTMCell(self.embedding_size, self.decoder_hidden_size)
        self.lstm = nn.LSTM(self.embedding_size, self.decoder_hidden_size, self.n_layers, dropout=p_dropout,batch_first = True)
        self.lin = nn.Linear(self.decoder_hidden_size, vocab_size)
        self.dropout = nn.Dropout(p_dropout)
       
    def forward_step(self, word_embedding, hidden_cell):
        # hidden_cell = (hidden, cell)
        # LSTMcell: (h_1, c_1) = self.lstm(input, (h_0, c_0))
        # LSTM: output, (h_n, c_n) = self.lstm(input, (h_0, c_0))
        # for LSTM input = word_embedding = [B x L x dim]
        
        output, new_hidden_cell = self.lstm(word_embedding, hidden_cell)
        # Shape of output = [B, 1, 128]
        output = output.squeeze(dim=1)
        # Shape of output = [B, 128]
        vocab_distrbtn = F.softmax(self.lin(output), dim=1)

        return vocab_distrbtn, (new_hidden_cell[0], new_hidden_cell[1])
        
    def forward(self, inpt, encoder_hidden, mask_Y, beta):
        t_max = inpt.shape[1]
        batch_size = inpt.shape[0]

        loss = 0
        # SOS = 1
        word = inpt[:,0] 
        # word shape = [B], convert it to [B x 1] to be used with nn.LSTM instead of nn.LSTMCell
        word = word.unsqueeze(1)        # shape = [B x 1]
        # word_embedding = self.embedding(word)
        word_embedding = self.dropout(self.embedding(word))     # shape = [B, 1, emb_dim]

        # encoder_hidden = (hidden, cell)
        hidden = encoder_hidden
        for t in range(t_max-1):
            vocab_dist, hidden = self.forward_step(word_embedding, hidden)  
            # vocab_dist = [B x V] = [32 x 30]
            word = torch.argmax(vocab_dist, dim=1) # word = [B, ]

            # DAgger policy = beta*oracle + (1-beta)*model
            u = random.uniform(0, 1)
            if u<=beta:
                # Teacher Forcing
                teach_input = inpt[:,t+1]  # shape = [B]
                teach_input = teach_input.unsqueeze(1)  # shape = [B x 1]
                word_embedding = self.dropout(self.embedding(teach_input))
            else:
                # Model's output as next input
                word = word.unsqueeze(1)        # word = [B x 1]
                word_embedding = self.dropout(self.embedding(word))
            
            # Cross Entropy Loss
            # ground truth B x 1 is the char at time step t+1 or t+1th column in B x L = 32 x L
            true_label = inpt[:,t+1]            
            # one hot encode the true label # B x 1 = 32 x 1 --> 32 x 30
            onehot = torch.zeros((batch_size, self.vocab_size))
            for i in range(batch_size):
                onehot[i][true_label[i]]=1
            # Cross entropy loss: vocab_dist B x 30, onehot B x 30
            NLL = (-1)*torch.log(vocab_dist)
            ce_loss = torch.sum(NLL*onehot, dim=1)
            loss += torch.sum(ce_loss*mask_Y[:,t]) 
        # averaged loss over the entire batch (except padding)
        return loss/torch.sum(mask_Y)

    def forward_inference(self, encoder_output):
        t_max = 80
        prediction_int = []
        # SOS = 1
        char = torch.ones(1)
        char = char.type(torch.LongTensor)
        char = char.unsqueeze(1)  # [1 x 1]
        # char_embedding = self.embedding(char)
        char_embedding = self.embedding(char) # shape = [B=1, 1, emb_dim]

        # Feed in the encoder_hidden
        hidden = encoder_output
        for t in range(t_max-1):
            vocab_dist, hidden = self.forward_step(char_embedding, hidden)  # vocab_dist = B x V = 10 x 30
            # vocab_dist shape: [B=1, 1, 30]
            vocab_dist = torch.squeeze(vocab_dist, dim=1)
            # vocab_dist shape: [B=1, 30]
            char = torch.argmax(vocab_dist, dim=1) # word = B x 1
            if char==2: 
                break
            prediction_int.append(int(char))
            # Model's output as next input
            char = char.unsqueeze(1)
            char_embedding = self.embedding(char) # shape = [B=1, 1, emb_dim]
            # char_embedding = self.embedding(char)

        return prediction_int

# class Seq2Seq_ScheduledSampling(nn.Module):
#     def __init__(self, vocab_size):
#         super(Seq2Seq_ScheduledSampling, self).__init__()
#         self.encoder = EncoderLSTM()
#         self.decoder = DecoderLSTM(vocab_size)

#     def forward(self, X_acoustic, Y_labels, Y_mask, beta):
#         encoder_output = self.encoder.forward(X_acoustic)
#         loss = self.decoder.forward(Y_labels, encoder_output, Y_mask, beta)
#         return loss

#     def forward_inference(self, acoustic_seq):
#         encoder_output = self.encoder.forward(acoustic_seq)
#         prediction = self.decoder.forward_inference(encoder_output)
#         return prediction

class Seq2Seq_ScheduledSampling(nn.Module):
    def __init__(self, vocab_size, n_layers, p_dropout):
        super(Seq2Seq_ScheduledSampling, self).__init__()
        self.encoder = EncoderLSTM_multilayer(n_layers, p_dropout)
        self.decoder = DecoderLSTM_multilayer(vocab_size, n_layers, p_dropout)

    def forward(self, X_acoustic, Y_labels, Y_mask, beta):
        encoder_output = self.encoder.forward(X_acoustic)
        loss = self.decoder.forward(Y_labels, encoder_output, Y_mask, beta)
        return loss

    def forward_inference(self, acoustic_seq):
        encoder_output = self.encoder.forward(acoustic_seq)
        prediction = self.decoder.forward_inference(encoder_output)
        return prediction
