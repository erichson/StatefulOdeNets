import torch
from .odenet import refine
from .helper import get_device
#
# helper functions to examine models
#
def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def train_for_epochs(model, loader,
                     criterion,
                     N_epochs, losses = None, 
                     lr=1.0e-3, lr_decay=0.2,
                     N_print=1000, device=None):
    "Works for normal models too"
    if device is None:
        device = get_device()
    if losses is None:
        losses = []
    #criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    step_count = 0
    for e in range(N_epochs):
        for imgs,labels in iter(loader):
            imgs = imgs.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            out = model(imgs)
            L = criterion(out,labels)
            L.backward()
            optimizer.step()
            losses.append(L.detach().cpu().item())
            if step_count % N_print == N_print-1:
                print(L.detach().cpu())
            step_count += 1
    return losses


def train_adapt(model, loader, criterion, N_epochs, N_refine,
               lr=1.0e-3, lr_decay=0.2, device=None):
    """I don't know how to control the learning rate"""
    if device is None:
        device = get_device()
    losses = []
    refine_steps = []
    model_list = [model]
    N_print= 10000
    for i in range(N_refine):
        # Adapt the learning rate as the network gets deeper
        gen_lr =  lr * 10.0**(-i//2)
        if i > 0:
            model_list.append(model_list[-1].refine())
            print("Adapting to ", count_parameters(model_list[-1]), "with lr = ",gen_lr)
        else:
            print("Starting with ",count_parameters(model_list[-1]), "with lr = ",gen_lr)
        losses = train_for_epochs(model_list[-1],loader, criterion,N_epochs,losses,
                                  lr = gen_lr, lr_decay=lr_decay, device=device)
        refine_steps.append(len(losses))
    return model_list, losses, refine_steps


from matplotlib import pylab as plt
def plot_weights_over_time(model_list, grab_w, grab_ts):
    for i,m in enumerate(model_list):
        w = grab_w(m).detach().numpy()
        ts =  grab_ts(m).detach().numpy()
        #print(ts.shape, w.shape)
        #plt.imshow(w[:,0,:].T)
        plt.subplot(len(model_list),1,i+1)
        dt = ts[1]-ts[0]
        plt.bar(ts[0:-1]+dt*0.5,w,width=ts[1]-ts[0],edgecolor='k')
        plt.xlabel('t')
    plt.show()

def plot_layers_over_times(model, img):
    y = models.channel_squish(img,2)
    with torch.no_grad():
        yy = torchdiffeq.odeint(m.net[0].net , y, m.net[0].ts)
    plt.figure(figsize=(8,20))
    L = yy.shape[0]
    for i in range(L):
        for j in range(4):
            plt.subplot(L,4,4*i+j+1)
            plt.imshow(yy[i,2,j,:,:])
    plt.show()