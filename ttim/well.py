import numpy as np
from scipy.special import kv,iv # Needed for K1 in Well class, and in CircInhom
import inspect # Used for storing the input
from .element import Element
from .equation import HeadEquation

class WellBase(Element):
    '''Well Base Class. All Well elements are derived from this class'''
    def __init__(self,model,xw=0,yw=0,rw=0.1,tsandbc=[(0.0,1.0)],res=0.0,layers=0,type='',name='WellBase',label=None):
        Element.__init__(self, model, Nparam=1, Nunknowns=0, layers=layers, tsandbc=tsandbc, type=type, name=name, label=label)
        self.Nparam = len(self.pylayers)  # Defined here and not in Element as other elements can have multiple parameters per layers
        self.xw = float(xw); self.yw = float(yw); self.rw = float(rw); self.res = res
        self.model.addElement(self)
    def __repr__(self):
        return self.name + ' at ' + str((self.xw,self.yw))
    def initialize(self):
        self.xc = np.array([self.xw + self.rw]); self.yc = np.array([self.yw]) # Control point to make sure the point is always the same for all elements
        self.Ncp = 1
        self.aq = self.model.aq.findAquiferData(self.xw,self.yw)
        self.setbc()
        coef = self.aq.coef[self.pylayers,:]
        laboverrwk1 = self.aq.lab / (self.rw * kv(1,self.rw/self.aq.lab))
        self.setflowcoef()
        self.term = -1.0 / (2*np.pi) * laboverrwk1 * self.flowcoef * coef  # shape (self.Nparam,self.aq.Naq,self.model.Np)
        self.term2 = self.term.reshape(self.Nparam,self.aq.Naq,self.model.Nin,self.model.Npin)
        self.strengthinf = self.flowcoef * coef
        self.strengthinflayers = np.sum(self.strengthinf * self.aq.eigvec[self.pylayers,:,:], 1) 
        self.resfach = self.res / ( 2*np.pi*self.rw*self.aq.Haq[self.pylayers] )  # Q = (h - hw) / resfach
        self.resfacp = self.resfach * self.aq.T[self.pylayers]  # Q = (Phi - Phiw) / resfacp
    def setflowcoef(self):
        '''Separate function so that this can be overloaded for other types'''
        self.flowcoef = 1.0 / self.model.p  # Step function
    def potinf(self,x,y,aq=None):
        '''Can be called with only one x,y value'''
        if aq is None: aq = self.model.aq.findAquiferData( x, y )
        rv = np.zeros((self.Nparam,aq.Naq,self.model.Nin,self.model.Npin),'D')
        if aq == self.aq:
            r = np.sqrt( (x-self.xw)**2 + (y-self.yw)**2 )
            pot = np.zeros(self.model.Npin,'D')
            if r < self.rw: r = self.rw  # If at well, set to at radius
            for i in range(self.aq.Naq):
                for j in range(self.model.Nin):
                    if r / abs(self.aq.lab2[i,j,0]) < self.Rzero:
                        pot[:] = kv(0, r / self.aq.lab2[i,j,:])
                        #quicker?
                        #bessel.k0besselv( r / self.aq.lab2[i,j,:], pot )
                        rv[:,i,j,:] = self.term2[:,i,j,:] * pot
        rv.shape = (self.Nparam,aq.Naq,self.model.Np)
        return rv
    def disinf(self,x,y,aq=None):
        '''Can be called with only one x,y value'''
        if aq is None: aq = self.model.aq.findAquiferData( x, y )
        qx,qy = np.zeros((self.Nparam,aq.Naq,self.model.Np),'D'), np.zeros((self.Nparam,aq.Naq,self.model.Np),'D')
        if aq == self.aq:
            qr = np.zeros((self.Nparam,aq.Naq,self.model.Nin,self.model.Npin),'D')
            r = np.sqrt( (x-self.xw)**2 + (y-self.yw)**2 )
            pot = np.zeros(self.model.Npin,'D')
            if r < self.rw: r = self.rw  # If at well, set to at radius
            for i in range(self.aq.Naq):
                for j in range(self.model.Nin):
                    if r / abs(self.aq.lab2[i,j,0]) < self.Rzero:
                        qr[:,i,j,:] = self.term2[:,i,j,:] * kv(1, r / self.aq.lab2[i,j,:]) / self.aq.lab2[i,j,:]
            qr.shape = (self.Nparam,aq.Naq,self.model.Np)
            qx[:] = qr * (x-self.xw) / r; qy[:] = qr * (y-self.yw) / r
        return qx,qy
    def headinside(self,t,derivative=0):
        '''Returns head inside the well for the layers that the well is screened in'''
        return self.model.head(self.xc,self.yc,t,derivative=derivative)[self.pylayers] - self.resfach[:,np.newaxis] * self.strength(t,derivative=derivative)
    def layout(self):
        return 'point',self.xw,self.yw
    
class DischargeWell(WellBase):
    '''Well with non-zero and potentially variable discharge through time'''
    def __init__(self,model,xw=0,yw=0,rw=0.1,tsandQ=[(0.0,1.0)],res=0.0,layers=0,label=None):
        self.storeinput(inspect.currentframe())
        WellBase.__init__(self,model,xw,yw,rw,tsandbc=tsandQ,res=res,layers=layers,type='g',name='DischargeWell',label=label)
        
class HeadWell(WellBase,HeadEquation):
    '''HeadWell of which the head varies through time. May be screened in multiple layers but all with the same head'''
    def __init__(self,model,xw=0,yw=0,rw=0.1,tsandh=[(0.0,1.0)],res=0.0,layers=0,label=None):
        self.storeinput(inspect.currentframe())
        WellBase.__init__(self,model,xw,yw,rw,tsandbc=tsandh,res=res,layers=layers,type='v',name='HeadWell',label=label)
        self.Nunknowns = self.Nparam
    def initialize(self):
        WellBase.initialize(self)
        self.parameters = np.zeros( (self.model.Ngvbc, self.Nparam, self.model.Np), 'D' )
        self.pc = self.aq.T[self.pylayers] # Needed in solving; We solve for a unit head