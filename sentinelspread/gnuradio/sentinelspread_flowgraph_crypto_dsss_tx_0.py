import numpy as np
from gnuradio import gr
from sentinelspread.gnuradio.blocks import crypto_dsss_tx as _TX

class blk(gr.sync_block):
    def __init__(self, message='SentinelSpread GNU Radio SDR Software Loopback Verification 2026', spreading_factor=16):
        gr.sync_block.__init__(self, name='crypto_dsss_tx', in_sig=None, out_sig=[np.complex64])
        self.impl = _TX(message=message, spreading_factor=spreading_factor)
    def work(self, input_items, output_items):
        return self.impl.work(input_items, output_items)
