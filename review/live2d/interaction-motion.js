/**
 * Authored pose timeline.
 *
 * Angles are in Live2D parameter units (degrees); hair/wing values are
 * normalised parameter values. The timeline is additive to the idle pose and
 * is intentionally gentle: the desktop pet is usually in peripheral vision.
 */
class SilverInteractionMotion {
 static smooth(a,b,t){const x=Math.max(0,Math.min(1,(t-a)/(b-a)));return x*x*(3-2*x);}
 static envelope(t,a,b,c,d){return this.smooth(a,b,t)*(1-this.smooth(c,d,t));}
 static pose(action,ms){
  const t=ms/1000,S=this.smooth.bind(this),E=this.envelope.bind(this);
  const p={angleX:0,angleY:0,angleZ:0,bodyX:0,bodyY:0,bodyZ:0,
   wing:0,hair:0,mouth:0,mouthForm:0,eyeSmile:0,brow:0,blink:null,
   arm:0,gazeX:0,gazeY:0,caption:''};
  if(action==='greeting'){
   const lift=E(t,.25,1.05,3.6,4.65);
   const wave=E(t,1,1.4,3.1,3.6)*Math.sin((t-1.15)*Math.PI*3.1);
   p.bodyZ=1.35*E(t,.05,.85,3.8,4.9);
   p.bodyX=.65*E(t,.15,.9,3.7,4.8);
   p.angleZ=-2.1*E(t,.4,1.3,3.7,4.8);
   p.angleY=1.9*E(t,.4,1.3,3.7,4.8);
   p.angleX=.65*E(t,.5,1.4,3.5,4.7)*Math.sin(t*2.2);
   // Leave the wing settle at its idle value during the greeting; a raised
   // hand should come from the arm mesh, not from folding both wings.
   p.wing=0;
   p.hair=.22*E(t,.4,1.3,3.7,4.9);
   p.mouth=(E(t,.75,.9,1.65,1.85)+E(t,2.25,2.4,3.1,3.3))*
    (.18+.28*Math.pow(Math.max(0,Math.sin(t*13)),.7));
   p.mouthForm=.18*E(t,.6,1.1,3.4,4.5);
   p.eyeSmile=.28*E(t,.55,1.2,3.4,4.6);
   p.brow=.05*E(t,.6,1.2,3.4,4.6);
   p.arm=-.55*lift+.10*wave;
   if(t>.65&&t<3.6)p.caption='嗨～我在这里！';
  }else if(action==='stretch'){
   const e=E(t,.1,1.5,3.1,5.2);
   p.angleY=-2.8*e;p.angleX=-.65*e;p.bodyX=.9*e;p.bodyZ=.45*e;
   p.wing=.26*e;p.hair=.24*e;p.mouthForm=.10*e;p.eyeSmile=.18*e;
   p.blink=.42*E(t,.7,1.4,2.5,3.4);
   if(t>.8&&t<4)p.caption='伸个懒腰～';
  }else if(action==='blink'){
   p.angleY=.75*E(t,.05,.35,.8,1.5);
   p.angleZ=.35*E(t,.1,.4,.9,1.6);
   p.bodyZ=.22*E(t,.15,.5,1,1.7);
   p.eyeSmile=.06*E(t,.2,.5,1,1.6);
   const blinkAge=ms<900?ms-180:ms-1080;
   p.blink=blinkAge>=0&&blinkAge<520?Math.pow(Math.sin(Math.PI*blinkAge/520),.6):0;
  }else if(action==='look'){
   // Eye tracking is exported in V26; no new head-turn rig is implied.
   const left=E(t,.25,1.0,1.5,2.2),right=E(t,2.0,2.7,3.4,4.5);
   p.gazeX=-.48*left+.40*right;p.gazeY=.10*E(t,.4,1.2,3.3,4.6);
   p.hair=.08*E(t,.5,1.3,3.4,4.7);p.eyeSmile=.05*right;
  }else if(action==='relax'){
   const e=E(t,.1,1.0,3.4,4.8);
   p.wing=.14*Math.sin(t*2.1)*e;p.hair=.16*Math.sin(t*1.8-.3)*e;
   p.gazeY=-.10*e;p.eyeSmile=.10*e;p.mouthForm=.08*e;
  }else if(action==='mouth'){
   const e=E(t,.2,.7,3.1,4.2);
   p.angleY=.8*e*Math.sin(t*2);
   p.angleX=.35*e;
   p.bodyX=.35*e;
   p.mouth=e*(.16+.34*Math.pow(Math.max(0,Math.sin(t*11)),.8))*
    (1-.85*E(t,1.4,1.6,1.9,2.1));
   p.mouthForm=.22*e;
   p.eyeSmile=.12*e;
   p.brow=.03*e;
   if(t>.5&&t<3.6)p.caption='今天也一起加油吧。';
  }
  return p;
 }
}
if(typeof module!=='undefined'&&module.exports)module.exports=SilverInteractionMotion;
