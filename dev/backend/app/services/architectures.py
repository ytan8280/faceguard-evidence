"""
Standalone model architectures for FaceGuard inference.

All classes are self-contained with no imports from training packages,
so they can be imported without triggering training registries.

To add a new architecture:
1. Define the nn.Module class here.
2. Register it in MODEL_REGISTRY inside model_service.py.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# Xception building blocks

class SeparableConv2d(nn.Module):
	def __init__(
		self,
		in_channels,
		out_channels,
		kernel_size=1,
		stride=1,
		padding=0,
		dilation=1,
		bias=False,
	):
		super().__init__()
		self.conv1 = nn.Conv2d(
			in_channels,
			in_channels,
			kernel_size,
			stride,
			padding,
			dilation,
			groups=in_channels,
			bias=bias,
		)
		self.pointwise = nn.Conv2d(
			in_channels,
			out_channels,
			1,
			1,
			0,
			1,
			1,
			bias=bias,
		)

	def forward(self, x):
		x = self.conv1(x)
		x = self.pointwise(x)
		return x


class Block(nn.Module):
	def __init__(
		self,
		in_filters,
		out_filters,
		reps,
		strides=1,
		start_with_relu=True,
		grow_first=True,
	):
		super().__init__()
		if out_filters != in_filters or strides != 1:
			self.skip = nn.Conv2d(in_filters, out_filters, 1, stride=strides, bias=False)
			self.skipbn = nn.BatchNorm2d(out_filters)
		else:
			self.skip = None

		self.relu = nn.ReLU(inplace=True)
		rep = []
		filters = in_filters

		if grow_first:
			rep.append(self.relu)
			rep.append(
				SeparableConv2d(
					in_filters,
					out_filters,
					3,
					stride=1,
					padding=1,
					bias=False,
				)
			)
			rep.append(nn.BatchNorm2d(out_filters))
			filters = out_filters

		for _ in range(reps - 1):
			rep.append(self.relu)
			rep.append(
				SeparableConv2d(
					filters,
					filters,
					3,
					stride=1,
					padding=1,
					bias=False,
				)
			)
			rep.append(nn.BatchNorm2d(filters))

		if not grow_first:
			rep.append(self.relu)
			rep.append(
				SeparableConv2d(
					in_filters,
					out_filters,
					3,
					stride=1,
					padding=1,
					bias=False,
				)
			)
			rep.append(nn.BatchNorm2d(out_filters))

		if not start_with_relu:
			rep = rep[1:]
		else:
			rep[0] = nn.ReLU(inplace=False)

		if strides != 1:
			rep.append(nn.MaxPool2d(3, strides, 1))
		self.rep = nn.Sequential(*rep)

	def forward(self, inp):
		x = self.rep(inp)
		skip = self.skip(inp) if self.skip is not None else inp
		if self.skip is not None:
			skip = self.skipbn(skip)
		return x + skip


# Xception

class Xception(nn.Module):
	"""Xception network (standalone, no registry dependency)."""

	def __init__(self, config: dict):
		super().__init__()
		self.num_classes = config["num_classes"]
		self.mode = config["mode"]
		inc = config["inc"]
		dropout = config["dropout"]

		# Entry flow
		self.conv1 = nn.Conv2d(inc, 32, 3, 2, 0, bias=False)
		self.bn1 = nn.BatchNorm2d(32)
		self.relu = nn.ReLU(inplace=True)
		self.conv2 = nn.Conv2d(32, 64, 3, bias=False)
		self.bn2 = nn.BatchNorm2d(64)

		self.block1 = Block(64, 128, 2, 2, start_with_relu=False, grow_first=True)
		self.block2 = Block(128, 256, 2, 2, start_with_relu=True, grow_first=True)
		self.block3 = Block(256, 728, 2, 2, start_with_relu=True, grow_first=True)

		# Middle flow
		self.block4 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block5 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block6 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block7 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block8 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block9 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block10 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block11 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)

		# Exit flow
		self.block12 = Block(728, 1024, 2, 2, start_with_relu=True, grow_first=False)
		self.conv3 = SeparableConv2d(1024, 1536, 3, 1, 1)
		self.bn3 = nn.BatchNorm2d(1536)
		self.conv4 = SeparableConv2d(1536, 2048, 3, 1, 1)
		self.bn4 = nn.BatchNorm2d(2048)

		self.last_linear = nn.Linear(2048, self.num_classes)
		if dropout:
			self.last_linear = nn.Sequential(
				nn.Dropout(p=dropout),
				nn.Linear(2048, self.num_classes),
			)

		self.adjust_channel = nn.Sequential(
			nn.Conv2d(2048, 512, 1, 1),
			nn.BatchNorm2d(512),
			nn.ReLU(inplace=True),
		)

	def features(self, x):
		x = self.conv1(x)
		x = self.bn1(x)
		x = self.relu(x)
		x = self.conv2(x)
		x = self.bn2(x)
		x = self.relu(x)

		x = self.block1(x)
		x = self.block2(x)
		x = self.block3(x)

		if self.mode != "shallow_xception":
			x = self.block4(x)
			x = self.block5(x)
			x = self.block6(x)
			x = self.block7(x)

		if self.mode == "shallow_xception":
			x = self.block12(x)
		else:
			x = self.block8(x)
			x = self.block9(x)
			x = self.block10(x)
			x = self.block11(x)
			x = self.block12(x)

		x = self.conv3(x)
		x = self.bn3(x)
		x = self.relu(x)
		x = self.conv4(x)
		x = self.bn4(x)

		if self.mode == "adjust_channel":
			x = self.adjust_channel(x)
		return x

	def classifier(self, features):
		x = self.relu(features)
		x = F.adaptive_avg_pool2d(x, (1, 1))
		x = x.view(x.size(0), -1)
		return self.last_linear(x)

	def forward(self, x):
		feat = self.features(x)
		out = self.classifier(feat)
		return out, feat


# FairDetector helper modules

class AdaIN(nn.Module):
	def __init__(self, eps=1e-5):
		super().__init__()
		self.eps = eps

	def c_norm(self, x, bs, ch, eps=1e-7):
		x_var = x.var(dim=-1) + eps
		x_std = x_var.sqrt().view(bs, ch, 1, 1)
		x_mean = x.mean(dim=-1).view(bs, ch, 1, 1)
		return x_std, x_mean

	def forward(self, x, y):
		size = x.size()
		bs, ch = size[:2]
		x_ = x.view(bs, ch, -1)
		y_ = y.reshape(bs, ch, -1)
		x_std, x_mean = self.c_norm(x_, bs, ch, eps=self.eps)
		y_std, y_mean = self.c_norm(y_, bs, ch, eps=self.eps)
		return ((x - x_mean.expand(size)) / x_std.expand(size)) * y_std.expand(size) + y_mean.expand(size)


class Conv2d1x1(nn.Module):
	def __init__(self, in_f, hidden_dim, out_f):
		super().__init__()
		self.conv2d = nn.Sequential(
			nn.Conv2d(in_f, hidden_dim, 1, 1),
			nn.LeakyReLU(inplace=True),
			nn.Conv2d(hidden_dim, hidden_dim, 1, 1),
			nn.LeakyReLU(inplace=True),
			nn.Conv2d(hidden_dim, out_f, 1, 1),
		)

	def forward(self, x):
		return self.conv2d(x)


class Head(nn.Module):
	def __init__(self, in_f, hidden_dim, out_f):
		super().__init__()
		self.do = nn.Dropout(0.2)
		self.pool = nn.AdaptiveAvgPool2d(1)
		self.mlp = nn.Sequential(
			nn.Linear(in_f, hidden_dim),
			nn.LeakyReLU(inplace=True),
			nn.Linear(hidden_dim, out_f),
		)

	def forward(self, x):
		bs = x.size(0)
		x_feat = self.pool(x).view(bs, -1)
		x = self.mlp(x_feat)
		x = self.do(x)
		return x, x_feat


def _r_double_conv(in_channels, out_channels):
	return nn.Sequential(
		nn.Conv2d(in_channels, out_channels, 3, padding=1),
		nn.ReLU(inplace=True),
		nn.Conv2d(out_channels, out_channels, 3, padding=1),
		nn.ReLU(inplace=True),
	)


class Conditional_UNet(nn.Module):
	"""Only needed so load_state_dict can map the checkpoint weights."""

	def __init__(self):
		super().__init__()
		self.upsample = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
		self.maxpool = nn.MaxPool2d(2)
		self.dropout = nn.Dropout(p=0.3)
		self.adain3 = AdaIN()
		self.adain2 = AdaIN()
		self.adain1 = AdaIN()
		self.dconv_up3 = _r_double_conv(512, 256)
		self.dconv_up2 = _r_double_conv(256, 128)
		self.dconv_up1 = _r_double_conv(128, 64)
		self.conv_last = nn.Conv2d(64, 3, 1)
		self.up_last = nn.Upsample(scale_factor=4, mode="bilinear", align_corners=True)
		self.activation = nn.Tanh()

	def forward(self, c, x):
		x = self.adain3(x, c)
		x = self.upsample(x)
		x = self.dropout(x)
		x = self.dconv_up3(x)
		c = self.upsample(c)
		c = self.dropout(c)
		c = self.dconv_up3(c)

		x = self.adain2(x, c)
		x = self.upsample(x)
		x = self.dropout(x)
		x = self.dconv_up2(x)
		c = self.upsample(c)
		c = self.dropout(c)
		c = self.dconv_up2(c)

		x = self.adain1(x, c)
		x = self.upsample(x)
		x = self.dropout(x)
		x = self.dconv_up1(x)

		x = self.conv_last(x)
		out = self.up_last(x)
		return self.activation(out)


# FairDetector (PG-FDD)

class FairDetector(nn.Module):
	"""
	Standalone FairDetector for inference.

	Uses 3 Xception backbones (forgery / content / fairness) with
	adjust_channel mode, plus multiple classification heads.
	"""

	def __init__(self):
		super().__init__()
		self.encoder_feat_dim = 512
		self.half_fingerprint_dim = self.encoder_feat_dim // 2

		xception_cfg = {"mode": "adjust_channel", "num_classes": 2, "inc": 3, "dropout": False}
		self.encoder_f = Xception(xception_cfg)
		self.encoder_c = Xception(xception_cfg)
		self.encoder_fair = Xception(xception_cfg)

		self.lr = nn.LeakyReLU(inplace=True)
		self.do = nn.Dropout(0.2)
		self.pool = nn.AdaptiveAvgPool2d(1)

		self.con_gan = Conditional_UNet()
		self.adain = AdaIN()

		self.head_spe = Head(self.half_fingerprint_dim, self.encoder_feat_dim, 4)
		self.head_sha = Head(self.half_fingerprint_dim, self.encoder_feat_dim, 2)
		self.head_fair = Head(self.half_fingerprint_dim, self.encoder_feat_dim, 6)
		self.head_fused = Head(self.half_fingerprint_dim, self.encoder_feat_dim, 1)

		self.block_spe = Conv2d1x1(
			self.encoder_feat_dim,
			self.half_fingerprint_dim,
			self.half_fingerprint_dim,
		)
		self.block_sha = Conv2d1x1(
			self.encoder_feat_dim,
			self.half_fingerprint_dim,
			self.half_fingerprint_dim,
		)
		self.block_fair = Conv2d1x1(
			self.encoder_feat_dim,
			self.half_fingerprint_dim,
			self.half_fingerprint_dim,
		)
		self.block_fused = Conv2d1x1(
			self.encoder_feat_dim,
			self.half_fingerprint_dim,
			self.half_fingerprint_dim,
		)

	def forward(self, data_dict: dict, inference=False) -> dict:
		image = data_dict["image"]
		f_all = self.encoder_f.features(image)
		c_all = self.encoder_c.features(image)
		fair_all = self.encoder_fair.features(image)

		f_spe = self.block_spe(f_all)
		f_share = self.block_sha(f_all)
		f_fair = self.block_fair(fair_all)
		fused_features = self.adain(f_fair, f_share)

		if inference:
			out_sha, sha_feat = self.head_sha(f_share)
			out_spe, spe_feat = self.head_spe(f_spe)
			out_fused, fused_feat = self.head_fused(fused_features)
			return {
				"cls_ag": out_sha,
				"feat": sha_feat,
				"cls": out_fused,
				"feat_fused": fused_feat,
			}

		# Training path (not used in inference service, included for
		# completeness so the full checkpoint can be loaded).
		f_concat = torch.cat((f_spe, f_share), dim=1)
		f2, f1 = f_concat.chunk(2, dim=0)
		c2, c1 = c_all.chunk(2, dim=0)
		rec1 = self.con_gan(f1, c1)
		rec2 = self.con_gan(f2, c2)
		cross1 = self.con_gan(f1, c2)
		cross2 = self.con_gan(f2, c1)

		out_spe, spe_feat = self.head_spe(f_spe)
		out_sha, sha_feat = self.head_sha(f_share)
		out_fair, fair_feat = self.head_fair(f_fair)
		out_fused, fused_feat = self.head_fused(fused_features)

		return {
			"cls_ag": out_sha,
			"feat": sha_feat,
			"cls_spe": out_spe,
			"feat_spe": spe_feat,
			"cls_fair": out_fair,
			"feat_fair": fair_feat,
			"cls": out_fused,
			"feat_fused": fused_feat,
			"feat_content": c_all,
			"recontruction_imgs": (cross1, cross2, rec1, rec2),
		}
