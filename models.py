import torch
import functools

#
# helper functions to examine models
#
def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

#
#
# Helper functions for making standard networks
#
def shallow(in_dim,hidden,out_dim,Act=torch.nn.ReLU):
    """Just make a shallow network. This is more of a macro."""
    return torch.nn.Sequential(
            torch.nn.Linear(in_dim,hidden),
            Act(),
            torch.nn.Linear(hidden,out_dim),
        )
def deep(widths,Act=torch.nn.ReLU):
    """Make a deep FCMLP given width specifications. Degenerates to a shallow layer if len(widths)==3"""
    layers = []
    for i in range(len(widths)-2):
        layers.extend([torch.nn.Linear(widths[i],widths[i+1]), Act()])
    layers.append(torch.nn.Linear(widths[-2],widths[-1]))
    return torch.nn.Sequential(*layers)
 
#
# Extra Building Blocks
#
class MultiLinear(torch.nn.Module):
    """Like Linear, but allows for higher ranks."""
    def __init__(self, in_dims, out_dims, bias=True):
        super(MultiLinear, self).__init__()
        self.in_dims = in_dims
        self.out_dims = out_dims
        in_features = functools.reduce(lambda x,y:x*y, in_dims)
        out_features = functools.reduce(lambda x,y:x*y, out_dims)
        self.net = torch.nn.Linear(in_features, out_features, bias=bias)
    def forward(self, x):
        xflat = torch.flatten(x, start_dim=-len(self.in_dims))
        hflat = self.net(xflat)
        return torch.reshape( hflat, hflat.shape[:-1]+self.out_dims )

class MultiLinearODE(MultiLinear):
    """MultiLinear with a t"""
    def __init__(self, *args, **kwargs):
        super(MultiLinearODE,self).__init__(*args,**kwargs)
    def forward(self, t, x):
        xflat = torch.flatten(x, start_dim=-len(self.in_dims))
        hflat = self.net(xflat)
        return torch.reshape( hflat, hflat.shape[:-1]+self.out_dims )
    
#
# Basic Classes
#
class ShallowNet(torch.nn.Module):
    """Just a basic shallow network"""
    def __init__(self, in_dim, out_dim, hidden=10, Act=torch.nn.ReLU):
        super(ShallowNet,self).__init__()
        self.net = shallow(in_dim,hidden,out_dim,Act=Act)
    def forward(self,x):
        return self.net(x)
    
class ShallowSkipNet(torch.nn.Module):
    """A basic shallow network with a skip connection"""
    def __init__(self, dim, hidden=10, Act=torch.nn.ReLU):
        super(ShallowSkipNet,self).__init__()
        self.net = shallow(dim,hidden,dim,Act=Act)
    def forward(self,x):
        return x+self.net(x)

class DeepNet(torch.nn.Module):
    """A deep network"""
    def __init__(self, dims, Act=torch.nn.ReLU):
        super(DeepNet,self).__init__()
        self.net = deep(dims,Act=Act)
    def forward(self,x):
        return self.net(x)
#
# Networks for ODEs. A different call structure
#
class ShallowODE(torch.nn.Module):
    """A basic shallow network that takes in a t as well"""
    def __init__(self, dim, hidden=10, Act=torch.nn.ReLU):
        super(ShallowODE,self).__init__()
        self.net = shallow(dim,hidden,dim,Act=Act)
    def forward(self,t,x):
        return self.net(x)
    
#
# RefineNet utilities 
#
import torchdiffeq
import copy

def refine(net):
    try:
        return net.refine()
    except AttributeError:
        if type(net) is torch.nn.Sequential:
            return torch.nn.Sequential(*[
                refine(m) for m in net
            ])
        else:
            #raise RuntimeError("Hit a network that cannot be refined.")
            # Error is for debugging. This makes sense too:
            return net

class ODEBlock(torch.nn.Module):
    """Wraps an ode-model with the odesolve to fit into standard 
    models."""
    def __init__(self,net,t_max=1.0,method='euler'):
        super(ODEBlock,self).__init__()
        self.t_max = t_max
        self.method = method
        self.ts = torch.tensor([0,t_max])
        self.net = net
    def forward(self,x):
        h = torchdiffeq.odeint(self.net, x, self.ts,
                               method=self.method)[1,:,:]
        #print(h.shape)
        return h
    def refine(self):
        """TODO: Cut self.net in half"""
        front_net = copy.deepcopy(self.net)
        back_net = copy.deepcopy(self.net)
        return torch.nn.Sequential(
            ODEBlock(front_net, self.t_max/2.0),
            ODEBlock(back_net,  self.t_max/2.0),
        )

class ODEModel(torch.nn.Module):
    def __init__(self,i_dim,o_dim,ode_width=4,
                 inside_width=4,Act=torch.nn.ReLU,
                method='euler'):
        super(ODEModel,self).__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(i_dim,ode_width),
            ODEBlock(
                ShallowODE(ode_width,hidden=inside_width,
                           Act=Act),
                method='euler'),
            #ODEBlock(ShallowODE(ode_width,hidden=12,Act=Act)),
            torch.nn.Linear(ode_width,o_dim),
        )
    def forward(self,x):
        # Missing sigmoid
        y = self.net(x)
        return y
    def refine(self):
        new = copy.deepcopy(self)
        new.net[1] = refine(self.net[1])
        return new
    
