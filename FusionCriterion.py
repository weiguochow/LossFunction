import torch
from torch.autograd import Function # This function is used to create the function class
import numpy as np
import ref

class FusionCriterion(Function):
  def __init__(self, regWeight, varWeight):  # Initialize the weight
    super(FusionCriterion, self).__init__()
    self.regWeight = regWeight
    self.varWeight = varWeight
   
   # Knowingt the connection relationship between skeletons
    self.skeletonRef = [[[0,1],    [1,2],
                         [3,4],    [4,5]],
                        [[10,11],  [11,12],
                         [13,14],  [14,15]], 
                         [[2, 6], [3, 6]], 
                         [[12,8], [13,8]]]
                         
    # Different weight between skeletons
    self.skeletonWeight = [[1.0085885098415446, 1, 
                            1, 1.0085885098415446], 
                           [1.1375361376887123, 1, 
                            1, 1.1375361376887123], 
                           [1, 1], 
                           [1, 1]]

    
  # input: [batchSize=6, ref.nJoints, 3]
  def forward(self, input, target_):
    target = target_.view(target_.size(0), ref.nJoints, 3)
    xy = target[:, :, :2] # xy coordinates of nJoints
    z = target[:, :, 2]   # depth of nJoints
    batchSize = target.size(0) # batchSize
    output = torch.FloatTensor(1) * 0 # Initialize output
    for t in range(batchSize):   # Every sample
      s = xy[t].sum()            # Summation of all the image coordinates
      if s < ref.eps and s > - ref.eps: #Sup data All the data is small
        loss = ((input[t] - z[t]) ** 2).sum() / ref.nJoints # average all the depth of joints
        output += self.regWeight * loss
      else:
        xy[t] = 2.0 * xy[t] / ref.outputRes - 1 # [0.0 2.0] - 1 = [-1.0 1.0]
        for g in range(len(self.skeletonRef)): # len(self.skeletonRef) = 3
          E, num = 0, 0
          N = len(self.skeletonRef[g]) # N = 4
          l = np.zeros(N)
          for j in range(N):  # N = 4
            id1, id2 = self.skeletonRef[g][j]  # Two points index of the connected skeletons
            if z[t, id1] > 0.5 and z[t, id2] > 0.5:
              l[j] = (((xy[t, id1] - xy[t, id2]) ** 2).sum() + (input[t, id1] - input[t, id2]) ** 2) ** 0.5 # The core formulation
              l[j] = l[j] * self.skeletonWeight[g][j]
              num += 1
              E += l[j]
          if num < 0.5:
            E = 0
          else:
            E = E / num
          loss = 0
          for j in range(N):
            if l[j] > 0:
              loss += (l[j] - E) ** 2 / num
          output += self.varWeight * loss 
    output = output / batchSize                 # Average the total loss over batchSize
    self.save_for_backward(input, target_)
    return output.cuda()
    
  # Backward part
  def backward(self, grad_output): # For this, the input element is grad_output
    input, target = self.saved_tensors
    target = target.view(target.size(0), ref.nJoints, 3)
    xy = target[:, :, :2]
    z = target[:, :, 2]
    grad_input = torch.zeros(input.size()) # Initialize the grad_input value
    batchSize = target.size(0)
    for t in range(batchSize):
      s = xy[t].sum()
      if s < ref.eps and s > - ref.eps:
        grad_input[t] += grad_output[0] * self.regWeight / batchSize * 2 / ref.nJoints * (input[t] - z[t]).cpu()
      else:
        xy[t] = 2.0 * xy[t] / ref.outputRes - 1
        for g in range(len(self.skeletonRef)):
          E, num = 0, 0
          N = len(self.skeletonRef[g])
          l = np.zeros(N)
          for j in range(N):
            id1, id2 = self.skeletonRef[g][j]
            if z[t, id1] > 0.5 and z[t, id2] > 0.5:
              l[j] = (((xy[t, id1] - xy[t, id2]) ** 2).sum() + (input[t, id1] - input[t, id2]) ** 2) ** 0.5
              l[j] = l[j] * self.skeletonWeight[g][j]
              num += 1
              E += l[j]
          if num < 0.5:
            E = 0
          else:
            E = E / num
          for j in range(N):
            if l[j] > 0:
              id1, id2 = self.skeletonRef[g][j]
              grad_input[t][id1] += 2 * self.varWeight * self.skeletonWeight[g][j] ** 2 / num * (l[j] - E) / l[j] * (input[t, id1] - input[t, id2]) / batchSize
              grad_input[t][id2] += 2 * self.varWeight * self.skeletonWeight[g][j] ** 2 / num * (l[j] - E) / l[j] * (input[t, id2] - input[t, id1]) / batchSize
    return grad_input.cuda(), None
    
    
    
    
