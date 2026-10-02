#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: SentinelSpread GNU Radio Software SDR Loopback
# Author: SentinelSpread Team
# Description: SentinelSpread GNU Radio Software SDR Loopback
# GNU Radio version: 3.10.12.0

from gnuradio import blocks
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import sentinelspread_flowgraph_epy_block_0 as epy_block_0  # embedded python block
import sentinelspread_flowgraph_epy_block_1 as epy_block_1  # embedded python block
import threading




class sentinelspread_flowgraph(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "SentinelSpread GNU Radio Software SDR Loopback", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.sps = sps = 4
        self.spreading_factor = spreading_factor = 16
        self.samp_rate = samp_rate = 200000
        self.rrc_taps = rrc_taps = filter.firdes.root_raised_cosine(2.0, 4.0, 1.0, 0.35, 41)

        ##################################################
        # Blocks
        ##################################################

        self.interp_fir_filter_xxx_0 = filter.interp_fir_filter_ccf(sps, rrc_taps)
        self.interp_fir_filter_xxx_0.declare_sample_delay(0)
        self.fir_filter_xxx_0 = filter.fir_filter_ccf(1, rrc_taps)
        self.fir_filter_xxx_0.declare_sample_delay(0)
        self.epy_block_1 = epy_block_1.blk(expected_message='SentinelSpread GNU Radio SDR Software Loopback Verification 2026', spreading_factor=spreading_factor)
        self.epy_block_0 = epy_block_0.blk(message='SentinelSpread GNU Radio SDR Software Loopback Verification 2026', spreading_factor=spreading_factor)
        self.digital_symbol_sync_xx_0 = digital.symbol_sync_cc(
            digital.TED_MUELLER_AND_MULLER,
            sps,
            0.045,
            1.0,
            1.0,
            1.5,
            1,
            digital.constellation_bpsk().base(),
            digital.IR_MMSE_8TAP,
            128,
            [])
        self.digital_costas_loop_cc_0 = digital.costas_loop_cc(0.0628, 2, False)
        self.channels_channel_model_0 = channels.channel_model(
            noise_voltage=0.02,
            frequency_offset=0.0,
            epsilon=1.0,
            taps=[1.0 + 0.0j],
            noise_seed=42,
            block_tags=False)
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_throttle_0, 0), (self.interp_fir_filter_xxx_0, 0))
        self.connect((self.channels_channel_model_0, 0), (self.fir_filter_xxx_0, 0))
        self.connect((self.digital_costas_loop_cc_0, 0), (self.epy_block_1, 0))
        self.connect((self.digital_symbol_sync_xx_0, 0), (self.digital_costas_loop_cc_0, 0))
        self.connect((self.epy_block_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.fir_filter_xxx_0, 0), (self.digital_symbol_sync_xx_0, 0))
        self.connect((self.interp_fir_filter_xxx_0, 0), (self.channels_channel_model_0, 0))


    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.digital_symbol_sync_xx_0.set_sps(self.sps)

    def get_spreading_factor(self):
        return self.spreading_factor

    def set_spreading_factor(self, spreading_factor):
        self.spreading_factor = spreading_factor

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.blocks_throttle_0.set_sample_rate(self.samp_rate)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps
        self.interp_fir_filter_xxx_0.set_taps(self.rrc_taps)
        self.fir_filter_xxx_0.set_taps(self.rrc_taps)




def main(top_block_cls=sentinelspread_flowgraph, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    tb.wait()


if __name__ == '__main__':
    main()
