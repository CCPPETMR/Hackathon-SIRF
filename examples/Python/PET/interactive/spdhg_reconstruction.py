# -*- coding: utf-8 -*-
###
# Demonstration of advanced PET reconstruction with CCP PET-MR Software
# and randomized algorithms
#
# This demonstration shows how to use the stochastic primal-dual hybrid 
# gradient algorithm (SPDHG) for regularized PET reconstruction.
#
#    [CERS2018] A. Chambolle, M. J. Ehrhardt, P. Richtarik and C.-B. Schoenlieb,
#    *Stochastic Primal-Dual Hybrid Gradient Algorithm with Arbitrary Sampling
#    and Imaging Applications*. SIAM Journal on Optimization, 28(4), 2783–2808
#    (2018) http://doi.org/10.1007/s10851-010-0251-1 
#
#    [E+2017] M. J. Ehrhardt, P. J. Markiewicz, P. Richtarik, J. Schott,
#    A. Chambolle and C.-B. Schoenlieb, *Faster PET reconstruction with a
#    stochastic primal-dual hybrid gradient method*. Wavelets and Sparsity XVII,
#    58 (2017) http://doi.org/10.1117/12.2272946.
#    
#    [EMS2018] M. J. Ehrhardt, P. J. Markiewicz and C.-B. Schoenlieb, *Faster 
#    PET Reconstruction with Non-Smooth Priors by Randomization and 
#    Preconditioning*. (2018) ArXiv: http://arxiv.org/abs/1808.07150
#
# This demo is a 'script', i.e. intended to be run step by step in a
# Python IDE such as spyder. It is organised in 'cells'. spyder displays these
# cells nicely and allows you to run each cell on its own.
#
# First version: 8th of September 2018
# Author: Matthias J Ehrhardt, Edoardo Pasca
#
## CCP PETMR Synergistic Image Reconstruction Framework (SIRF)
## Copyright 2015 - 2018 Rutherford Appleton Laboratory STFC
## Copyright 2015 - 2018 University College London.
##
## This is software developed for the Collaborative Computational
## Project in Positron Emission Tomography and Magnetic Resonance imaging
## (http://www.ccppetmr.ac.uk/).
##
## Licensed under the Apache License, Version 2.0 (the "License");
##   you may not use this file except in compliance with the License.
##   You may obtain a copy of the License at
##       http://www.apache.org/licenses/LICENSE-2.0
##   Unless required by applicable law or agreed to in writing, software
##   distributed under the License is distributed on an "AS IS" BASIS,
##   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
##   See the License for the specific language governing permissions and
##   limitations under the License.

# Initial imports etc
import numpy
import matplotlib.pyplot as plt
import os
import shutil
#import scipy
#from scipy import optimize
import pSTIR as pet
# plotting settings
plt.ion() # interactive 'on' such that plots appear during loops
# some handy function definitions

def imshow3(image, slice=None, **kwargs):
    im = image.as_array()
    
    if slice is None:
        slice = im.shape[0]/2
        
    imshow(im[slice, :, :], **kwargs)   
    
def imshow(image, newfig=True, limits=None, title=''):
    """Usage: imshow(image, [min,max], title)"""
    if newfig:
        plt.figure()

    plt.title(title)

    bitmap=plt.imshow(image)
    if limits is None:
        limits=[image.min(),image.max()]
                
    plt.clim(limits[0], limits[1])
    plt.colorbar(shrink=.6)
    plt.axis('off');
    return bitmap

# go to directory with input files
# adapt this path to your situation (or start everything in the relevant directory)
os.chdir(pet.petmr_data_path('pet'))
# copy files to working folder and change directory to where the output files are
shutil.rmtree('working_folder/thorax_single_slice',True)
shutil.copytree('thorax_single_slice','working_folder/thorax_single_slice')
os.chdir('working_folder/thorax_single_slice')

# We will first create some simulated data from ground-truth images

# Read in images
image = pet.ImageData('emission.hv');
image_array=image.as_array()*.05
image.fill(image_array);
mu_map = pet.ImageData('attenuation.hv');
mu_map_array=mu_map.as_array();
# bitmap display of images
slice=image_array.shape[0]/2;
plt.figure();
imshow(image_array[slice,:,:,], title='emission image');

# save max for future displays
cmax = image_array.max()*.6

# create acquisition model
am = pet.AcquisitionModelUsingRayTracingMatrix()
am.set_num_tangential_LORs(5)
templ = pet.AcquisitionData('template_sinogram.hs')
am.set_up(templ,image); 
# simulate some data using forward projection
acquired_data=am.forward(image)
acquisition_array = acquired_data.as_array()

# Display bitmaps of a middle sinogram
plt.figure()
imshow(acquisition_array[0,:,:,], title='Forward projection')

# close all plots
plt.close('all')

#%% create TBC reconstructor

import pCIL  # the code from this module needs to be imported somehow differently
from ccpi.optimisation.funcs import ZeroFun, IndicatorBox  # IndicatorBox does currently not work for SIRF
#from ccpi.filters.regularisers import FGP_TV

# IndicatorBox does currently not work for SIRF
#g_reg = IndicatorBox(lower=0,upper=1)               
#x = g_reg.prox(image, 1)


data = acquired_data
background = data.copy()
background.fill(5)

array = data.as_array() + background.as_array()
noisy_array = numpy.random.poisson(array.astype('float64'))
max_counts = noisy_array.max()
print(' Maximum counts in the data: {}'.format(noisy_array.max()))
noisy_data = data.clone()
noisy_data.fill(noisy_array);

g_noreg = ZeroFun()

# the FGP_TV will output a CCPi DataContainer not a SIRF one, so 
# we will need to wrap it in something compatible
from plugins.regularisers import FGP_TV  # needs to be properly imported
class FGP_TV_SIRF(FGP_TV):
    def prox(self, x, sigma):
       print("calling FGP")
       out = super(FGP_TV_SIRF, self).prox(x, sigma)
       y = x.copy()
       y.fill(out.as_array())
       return y

g_reg = FGP_TV_SIRF(lambdaReg=.5,
                iterationsTV=200,
                tolerance=1e-5,
                methodTV=0,
                nonnegativity=1,
                printing=0,
                device='cpu')

class OperatorSubsetPET():
    
    def __init__(self, op, subset_num, num_subsets):
        self.__op__ = op
        self.__subset_num__ = subset_num
        self.__num_subsets__ = num_subsets
        
        x = op.img_templ.copy()
        x.fill(1)
        y = self.forward_sirf(x).as_array()
        self.ind = numpy.nonzero(y.flatten())[0]
    
    def forward_sirf(self, x):
        return self.__op__.forward(x, subset_num=self.__subset_num__, 
                                   num_subsets=self.__num_subsets__)

    def __call__(self, x):
        y = self.__op__.forward(x, subset_num=self.__subset_num__, 
                                   num_subsets=self.__num_subsets__)
        return self.sirf2sub(y)

    def direct(self, x):
        return self(x)
    
    def forward(self, x):
        return self(x)
           
    def adjoint(self, x):
        x = self.sub2sirf(x)
        return self.__op__.backward(x, subset_num=self.__subset_num__, 
                                    num_subsets=self.__num_subsets__)
        
    def allocate_direct(self, x=None):
#        y = self.__op__.acq_templ.create_uniform_image()
        y = self.__op__.img_templ.copy()
        if x is not None:
            y.fill(x)
        return y
    
    def allocate_adjoint(self, x=None):
#        y = self.__op__.acq_templ.get_uniform_copy()
        y = pet.AcquisitionData(self.__op__.acq_templ)
        if x is not None:
            y.fill(x)
        return self.sirf2sub(y)
        
    def sub2sirf(self, x):
        y = pet.AcquisitionData(self.__op__.acq_templ)
        y.fill(0)
        y_array = y.as_array().flatten()
        y_array[self.ind] = x
        y.fill(y_array)
        return y
                
    def sirf2sub(self, x):
        return x.as_array().flatten()[self.ind]
            
#class SubsetOperator():
#    
#    def __init__(self, op, nsubsets):
#        self.__op__ = op
#        self.__nsubsets__ = nsubsets
#        
#    def __len__(self):
#        return self.__nsubsets__
#    
#    def __call__(self, x):
#        return self.__op__.forward(x)
#    
#    def adjoint(self, x):
#        return self.__op__.backward(x)
#    
#    def __ind__(self, i):
#        return OperatorInd(self.__op__, i, len(self))
    

def OperatorSubsetsPET(op, num_subsets):
    return [OperatorSubsetPET(op, ind, num_subsets) 
            for ind in range(num_subsets)]
        
num_subsets = 16
num_epochs = 5
num_iter = num_epochs * num_subsets

A = OperatorSubsetsPET(am, num_subsets)
A_norms = [1.05 * pCIL.PowerMethodNonsquare(Ai, 10, x0=image.copy()) 
           for Ai in A]

As = OperatorSubsetsPET(am, num_subsets)
As_norms = [1.05 * pCIL.PowerMethodNonsquare(Ai, 10, x0=image.copy()) 
               for Ai in As]

f = [pCIL.KullbackLeibler(op.sirf2sub(noisy_data), op.sirf2sub(background)) 
     for op in A]

fs = [pCIL.KullbackLeibler(op.sirf2sub(noisy_data), op.sirf2sub(background)) 
     for op in As]


#%%
recon_subsets_noreg = pCIL.spdhg(fs, g_noreg, As, A_norms=As_norms)

# %%
for i in range(num_iter):
    print(recon_subsets_noreg.iter)
    recon_subsets_noreg.update()

#%%
recon_reg = pCIL.spdhg(f, g_reg, A, A_norms=A_norms)

# %%
for i in range(num_epochs):
    print(recon_reg.iter)
    recon_reg.update()

#%%
recon_subsets_reg = pCIL.spdhg(fs, g_reg, As, A_norms=As_norms)

# %%
for i in range(num_iter):
    print(recon_subsets_reg.iter)
    recon_subsets_reg.update()

#%%  show result      
plt.figure()

plt.subplot(1, 3, 1)
imshow3(recon_subsets_noreg.x, limits=[-0.3, cmax], 
        newfig=False, title='recon subsets noreg')
plt.subplot(1, 3, 2)

imshow3(recon_reg.x, limits=[-0.3, cmax],
        newfig=False, title='recon reg')

plt.subplot(1, 3, 3)
imshow3(recon_subsets_reg.x, limits=[-0.3, cmax], 
        newfig=False, title='recon subsets reg')
