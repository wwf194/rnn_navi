#from Models.LSTM_Navi import LSTM_Navi
#from Models.RSLP_LIF import RSLP_LIF
#from Models.Linear_Navi import Linear_Navi
#from Models.place_cells import PlaceCells
#import Models.RNN_LIF import rnn_lif
import Models.rnn_lif

def build_module(module):
    if module.type in ["LeakySingleLayer"]:
        # to be implemented
        pass
    else:
        raise utils_torch.model.build_module(module)


