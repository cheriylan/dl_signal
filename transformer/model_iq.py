import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir) 

import torch
from torch import nn
import torch.nn.functional as F
import numpy as np
from modules.transformer import TransformerEncoder, TransformerDecoder
from models import *
from utils import count_parameters

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


class TransformerModel(nn.Module):
    def __init__(self, time_step, input_dims, hidden_size, embed_dim, output_dim, num_heads, attn_dropout, relu_dropout, res_dropout, out_dropout, layers, attn_mask=False):
        """
        Construct a basic Transfomer model.
        
        :param input_dims: The input dimensions of the various modalities.
        :param hidden_size: The hidden dimensions of the fc layer.
        :param embed_dim: The dimensions of the embedding layer.
        :param output_dim: The dimensions of the output (128 in MuiscNet).
        :param num_heads: The number of heads to use in the multi-headed attention. 
        :param attn_dropout: The dropout following self-attention sm((QK)^T/d)V.
        :param relu_droput: The dropout for ReLU in residual block.
        :param res_dropout: The dropout of each residual block.
        :param out_dropout: The dropout of output layer.
        :param layers: The number of transformer blocks.
        :param attn_mask: A boolean indicating whether to use attention mask (for transformer decoder).
        """
        super(TransformerModel, self).__init__()
        [self.orig_d_a, self.orig_d_b] = input_dims
        assert self.orig_d_a == self.orig_d_b
        self.d_a, self.d_b = 512, 512 
        final_out = embed_dim * 2
        h_out = hidden_size
        self.num_heads = num_heads
        self.layers = layers
        self.attn_dropout = attn_dropout
        self.relu_dropout = relu_dropout
        self.res_dropout = res_dropout
        self.attn_mask = attn_mask
        self.embed_dim = embed_dim
        
        # Transformer networks
        self.trans = self.get_network()
        print("Encoder Model size: {0}".format(count_parameters(self.trans)))
        self.fc_a = nn.Linear(self.orig_d_a, self.d_a)
        self.fc_b = nn.Linear(self.orig_d_b, self.d_b)
        # Projection layers
        self.proj = ComplexLinear(self.d_a, self.embed_dim)
        
        self.out_fc1 = nn.Linear(final_out, h_out)
        
        self.out_fc2 = nn.Linear(h_out, output_dim)
        
        self.out_dropout = nn.Dropout(out_dropout)
    def get_network(self):
        
        return TransformerEncoder(embed_dim=self.embed_dim, num_heads=self.num_heads, layers=self.layers, attn_dropout=self.attn_dropout,
            relu_dropout=self.relu_dropout, res_dropout=self.res_dropout, attn_mask=self.attn_mask)
            
    def forward(self, x):
        """
        x should have dimension [seq_len, batch_size, n_features] (i.e., L, N, C).
        """
        time_step, batch_size, n_features = x.shape

        input_a = x[:, :, :n_features//2]
        input_b = x[:, :, n_features//2:]
        """Add linear layer here"""
        input_a = self.fc_a(input_a)
        input_b = self.fc_b(input_b)
        input_a, input_b = self.proj(input_a, input_b)
        h_as, h_bs = self.trans(input_a, input_b)
        h_concat = torch.cat([h_as[-1], h_bs[-1]], dim=-1)
        output = self.out_fc2(self.out_dropout(F.relu(self.out_fc1(h_concat))))
        return output

class TransformerGenerationModel(nn.Module):
    def __init__(self, input_dims, hidden_size, embed_dim, output_dim, num_heads, attn_dropout, relu_dropout, res_dropout, out_dropout, layers, attn_mask=False, src_mask=False, tgt_mask=False):
        super(TransformerGenerationModel, self).__init__()
        [self.orig_d_a, self.orig_d_b] = input_dims
        assert self.orig_d_a == self.orig_d_b
        self.d_a, self.d_b = 512, 512
        final_out = embed_dim * 2
        h_out = hidden_size
        self.num_heads = num_heads
        self.layers = layers
        self.attn_dropout = attn_dropout
        self.relu_dropout = relu_dropout
        self.res_dropout = res_dropout
        self.attn_mask = attn_mask
        self.embed_dim = embed_dim

        self.d_a, self.d_b = 512, 512
        self.fc_a = nn.Linear(self.orig_d_a, self.d_a)
        self.fc_b = nn.Linear(self.orig_d_b, self.d_b)
        
        self.trans_encoder = self.get_encoder_network()
        self.trans_decoder = self.get_decoder_network()

        print("Encoder Model size: {0}".format(count_parameters(self.trans_encoder)))
        print("Decoder Model size: {0}".format(count_parameters(self.trans_decoder)))
        
        # Projection layers
        self.proj_enc = ComplexLinear(self.d_a, self.embed_dim)
        self.proj_dec = ComplexLinear(self.orig_d_a, self.embed_dim)
        
        self.out_fc1 = nn.Linear(final_out, h_out)
        
        self.out_fc2 = nn.Linear(h_out, output_dim)
  
        self.out_fc3 = nn.Linear(output_dim, 1000)
        
        self.out_dropout = nn.Dropout(out_dropout)

    def get_encoder_network(self):
        
        return TransformerEncoder(embed_dim=self.embed_dim, num_heads=self.num_heads, layers=self.layers, attn_dropout=self.attn_dropout,
            relu_dropout=self.relu_dropout, res_dropout=self.res_dropout, attn_mask=self.attn_mask)

    def get_decoder_network(self): 
        return TransformerDecoder(embed_dim=self.embed_dim, num_heads=self.num_heads, layers=self.layers, src_attn_dropout=self.attn_dropout, 
            relu_dropout=self.relu_dropout, res_dropout=self.res_dropout, tgt_attn_dropout=self.attn_dropout)
            
    def forward(self, x, y=None, max_len=None):
        """
        x should have dimension [seq_len, batch_size, n_features] (i.e., L, N, C).
        """
        time_step, batch_size, n_features = x.shape
        input_a = x[:, :, :n_features//2]
        input_b = x[:, :, n_features//2:]
        """Add linear layer here"""
        input_a = self.fc_a(input_a)
        input_b = self.fc_b(input_b)
        input_a, input_b = self.proj_enc(input_a, input_b)
        h_as, h_bs = self.trans_encoder(input_a, input_b)
        if y is not None:
            seq_len, batch_size, n_features2 = y.shape 
            n_features = n_features2 // 2
            y_a = y[:-1, :, :self.orig_d_a]                               # truncate last target 
            y_b = y[:-1, :, self.orig_d_a: self.orig_d_a + self.orig_d_b] # truncate last target 
            sos_a = torch.zeros(1, batch_size, n_features).cuda()
            sos_b = torch.zeros(1, batch_size, n_features).cuda()
            y_a = torch.cat([sos_a, y_a], dim=0)    # add <sos> to front 
            y_b = torch.cat([sos_b, y_b], dim=0)    # add <sos> to front 
            y_a, y_b = self.proj_dec(y_a, y_b)
            out_as, out_bs = self.trans_decoder(input_A=y_a, input_B=y_b, enc_A=h_as, enc_B=h_bs)
            out_concat = torch.cat([out_as, out_bs], dim=-1)
            output = self.out_fc2(self.out_dropout(F.relu(self.out_fc1(out_concat))))

        elif max_len is not None:
            dec_a = torch.zeros(1, batch_size, n_features//2).cuda()
            dec_b = torch.zeros(1, batch_size, n_features//2).cuda()
            dec_a, dec_b = self.proj_dec(dec_a, dec_b)

            dec_a, dec_b = self.trans_decoder(input_A=dec_a, input_B=dec_b, enc_A=h_as, enc_B=h_bs) 
            y_a, y_b = dec_a, dec_b

            for i in range(max_len - 1):
                dec_a, dec_b = self.trans_decoder(input_A=y_a, input_B=y_b, enc_A=h_as, enc_B=h_bs)
                y_a, y_b = torch.cat([y_a, dec_a[-1].unsqueeze(0)], dim=0), torch.cat([y_b, dec_b[-1].unsqueeze(0)], dim=0)
            out_concat = torch.cat([y_a, y_b], dim=-1)
            output = self.out_fc2(self.out_dropout(F.relu(self.out_fc1(out_concat))))
        output = F.relu(self.out_fc3(output[-1])) # use last time step to generate a label for entire sequence

        return output
