"""
TaikoNation TF1 Checkpoint -> PyTorch Weights Converter
"""

import os
import numpy as np
import torch
import torch.nn as nn

def read_varint(buf, p):
    res, shift = 0, 0
    while p < len(buf):
        b = buf[p]; p += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return res, p

def parse_proto(b):
    p, fields = 0, {}
    while p < len(b):
        key, p = read_varint(b, p)
        wire, fnum = key & 7, key >> 3
        if wire == 0: v, p = read_varint(b, p)
        elif wire == 1: v = b[p:p+8]; p += 8
        elif wire == 2:
            l, p = read_varint(b, p)
            v = b[p:p+l]; p += l
        elif wire == 5: v = b[p:p+4]; p += 4
        else: raise ValueError(f"Wire {wire}")
        fields.setdefault(fnum, []).append(v)
    return fields

def parse_shape(proto_bytes):
    f = parse_proto(proto_bytes)
    dims = []
    if 2 in f:
        for dim_bytes in f[2]:
            df = parse_proto(dim_bytes)
            dims.append(df.get(1, [0])[0])
    return dims

def extract_weights(model_dir="output/model"):
    index_file = os.path.join(model_dir, "model.tfl.index")
    data_file = os.path.join(model_dir, "model.tfl.data-00000-of-00001")
    
    with open(index_file, "rb") as f:
        idx = f.read()
    with open(data_file, "rb") as f:
        data = f.read()

    weights = {}
    pos = 0
    key = b""
    while pos < len(idx) - 48:
        shared, pos = read_varint(idx, pos)
        unshared, pos = read_varint(idx, pos)
        vlen, pos = read_varint(idx, pos)
        key_delta = idx[pos:pos+unshared]; pos += unshared
        val = idx[pos:pos+vlen]; pos += vlen
        key = key[:shared] + key_delta
        vf = parse_proto(val)
        if 4 in vf and 5 in vf and b"Adam" not in key and b"avg" not in key and b"Step" not in key and b"val_" not in key and b"is_" not in key:
            offset = vf[4][0]
            size = vf[5][0]
            shape = parse_shape(vf.get(2, [b""])[0])
            arr = np.frombuffer(data[offset:offset+size], dtype=np.float32).copy()
            if shape:
                arr = arr.reshape(shape)
            weights[key.decode()] = arr
            print(f"Extracted: {key.decode()}, shape: {arr.shape}")
            
    return weights

class TaikoNationNet(nn.Module):
    def __init__(self, weights=None):
        super().__init__()
        # 1D-CNN (TF: Conv1D_1 kernel size 3, 80->32 filters)
        self.conv = nn.Conv1d(80, 32, kernel_size=3, padding=1)
        self.max_pool = nn.MaxPool1d(kernel_size=2, stride=2, padding=0)
        
        # Fully Connected (TF: 256 -> 128)
        self.fc_encoder = nn.Linear(256, 128)
        
        # LSTM_1 (TF: 16 in_features -> 64 hidden_size)
        self.lstm = nn.LSTM(16, 64, batch_first=True)
        
        # Softmax classifier (TF: 64 -> 28, reshaped to [4, 7])
        self.fc_out = nn.Linear(64, 28)

        if weights:
            self.load_tf_weights(weights)

    def load_tf_weights(self, weights):
        # Conv1D_1/W: [3, 1, 80, 32] -> PyTorch Conv1d weight: [32, 80, 3]
        w_conv = torch.from_numpy(weights["Conv1D_1/W"]).squeeze(1).permute(2, 1, 0)
        b_conv = torch.from_numpy(weights["Conv1D_1/b"])
        self.conv.weight.data.copy_(w_conv)
        self.conv.bias.data.copy_(b_conv)

        # FullyConnected/W: [256, 128] -> PyTorch Linear: [128, 256]
        w_fc = torch.from_numpy(weights["FullyConnected/W"]).t()
        b_fc = torch.from_numpy(weights["FullyConnected/b"])
        self.fc_encoder.weight.data.copy_(w_fc)
        self.fc_encoder.bias.data.copy_(b_fc)

        # LSTM_1 weights
        # TF matrix: [80, 256] (16 in + 64 hidden)
        w_lstm = torch.from_numpy(weights["LSTM_1/LSTM_1/BasicLSTMCell/Linear/Matrix"])
        b_lstm = torch.from_numpy(weights["LSTM_1/LSTM_1/BasicLSTMCell/Linear/Bias"])
        # TF: i, j(g), f, o
        i_w, j_w, f_w, o_w = w_lstm.split(64, dim=1)
        i_b, j_b, f_b, o_b = b_lstm.split(64, dim=0)
        # PyTorch: i, f, g, o
        pt_w = torch.cat([i_w, f_w, j_w, o_w], dim=1).t()
        pt_b = torch.cat([i_b, f_b, j_b, o_b], dim=0)
        
        self.lstm.weight_ih_l0.data.copy_(pt_w[:, :16])
        self.lstm.weight_hh_l0.data.copy_(pt_w[:, 16:])
        self.lstm.bias_ih_l0.data.copy_(pt_b)
        self.lstm.bias_hh_l0.data.zero_()

        # Output FC: [64, 28] -> [28, 64]
        w_out = torch.from_numpy(weights["FullyConnected_1/W"]).t()
        b_out = torch.from_numpy(weights["FullyConnected_1/b"])
        self.fc_out.weight.data.copy_(w_out)
        self.fc_out.bias.data.copy_(b_out)

    def forward(self, song_encoder_in):
        # song_encoder_in: [batch, 8, 16]
        lstm_out, _ = self.lstm(song_encoder_in) # [batch, 8, 64]
        last_step = lstm_out[:, -1, :] # [batch, 64]
        logits = self.fc_out(last_step) # [batch, 28]
        probs = torch.softmax(logits, dim=-1) # [batch, 28]
        return probs.view(-1, 4, 7) # [batch, 4, 7]

    def encode_song(self, song_chunk):
        # song_chunk: [batch, 16, 80]
        x = song_chunk.permute(0, 2, 1) # [batch, 80, 16]
        x = torch.relu(self.conv(x)) # [batch, 32, 16]
        x = self.max_pool(x) # [batch, 32, 8]
        # TF flattens NHWC: in TF shape was [batch, 8, 1, 32] flattened to [batch, 256]
        # x here is [batch, 32, 8], transpose to [batch, 8, 32] then flatten
        x = x.permute(0, 2, 1).contiguous().view(-1, 256) # [batch, 256]
        x = torch.relu(self.fc_encoder(x)) # [batch, 128]
        return x.view(-1, 8, 16) # [batch, 8, 16]

if __name__ == "__main__":
    weights = extract_weights("output/model")
    model = TaikoNationNet(weights)
    torch.save(model.state_dict(), "output/model/taiko_nation_pytorch.pt")
    print("PyTorch model saved successfully to output/model/taiko_nation_pytorch.pt!")
