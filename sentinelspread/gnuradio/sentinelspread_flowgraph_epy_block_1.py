import numpy as np
from gnuradio import gr
import sentinelspread.gnuradio.blocks as ssb
import pmt

class blk(gr.sync_block):
    def __init__(self, expected_message='SentinelSpread GNU Radio SDR Software Loopback Verification 2026', spreading_factor=16):
        gr.sync_block.__init__(self, name='dsss_crypto_rx', in_sig=[np.complex64], out_sig=None)
        self.impl = ssb.dsss_crypto_rx(expected_message=expected_message, spreading_factor=spreading_factor)
        self.message_port_register_out(pmt.intern('msg_out'))
    def work(self, input_items, output_items):
        return self.impl.work(input_items, output_items)
    def stop(self):
        self.impl.stop()
        return super().stop()
