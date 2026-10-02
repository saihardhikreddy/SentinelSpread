import numpy as np
from gnuradio import gr
from sentinelspread.gnuradio.blocks import dsss_crypto_rx as _RX

class blk(gr.sync_block):
    def __init__(self, expected_message='SentinelSpread GNU Radio SDR Software Loopback Verification 2026', spreading_factor=16):
        gr.sync_block.__init__(self, name='dsss_crypto_rx', in_sig=[np.complex64], out_sig=None)
        self.impl = _RX(expected_message=expected_message, spreading_factor=spreading_factor)
    def work(self, input_items, output_items):
        return self.impl.work(input_items, output_items)
    def stop(self):
        self.impl.stop()
        return super().stop()
