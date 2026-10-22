/** Authored pose timeline; coordinates use the 1086 x 1448 source canvas. */
class SilverInteractionMotion {
 static smooth(a,b,t){const x=Math.max(0,Math.min(1,(t-a)/(b-a)));return x*x*(3-2*x);}
 static envelope(t,a,b,c,d){return this.smooth(a,b,t)*(1-this.smooth(c,d,t));}
 static pose(action,ms){
  const t=ms/1000,S=this.smooth.bind(this),E=this.envelope.bind(this);
  const p={lean:0,head:0,arm:0,otherArm:0,wing:0,tail:0,mouth:0,blink:null,caption:''};
  if(action==='greeting'){
   const lift=E(t,.25,1.05,3.6,4.65),wave=E(t,1,1.4,3.1,3.6)*Math.sin((t-1.15)*Math.PI*3.1);
   p.lean=-.042*E(t,.05,.85,3.8,4.9);p.head=.055*E(t,.4,1.3,3.7,4.8);
   p.arm=-1.12*lift+.13*wave;p.otherArm=.06*E(t,.4,1.1,3.4,4.7);
   p.tail=.045*E(t,.5,1.5,4,5.1)*Math.sin(t*2.4);p.wing=.10*E(t,.5,1.5,3.4,4.8);
   p.mouth=(E(t,.75,.9,1.65,1.85)+E(t,2.25,2.4,3.1,3.3))*(.25+.35*Math.pow(Math.max(0,Math.sin(t*13)),.7));
   if(t>.65&&t<3.6)p.caption='嗨～我在这里！';
  }else if(action==='stretch'){
   const e=E(t,.1,1.5,3.1,5.2);p.arm=-.22*e;p.otherArm=.22*e;
   p.lean=.015*e;p.head=-.035*e;p.wing=.18*e;p.tail=-.05*E(t,.5,2,3.4,5.6);
   if(t>1&&t<3.1)p.blink=.55;if(t>.8&&t<4)p.caption='伸个懒腰～';
  }else if(action==='blink'){
   p.head=.018*E(t,.05,.35,.8,1.5);p.lean=-.008*E(t,.15,.5,1,1.7);
   p.blink=1-E(t,.14,.25,.31,.49)-E(t,.77,.89,.95,1.14);
  }else if(action==='mouth'){
   const e=E(t,.2,.7,3.1,4.2);p.head=.018*e*Math.sin(t*2);p.lean=-.009*e;
   p.mouth=e*(.18+.36*Math.pow(Math.max(0,Math.sin(t*11)),.8))*(1-.85*E(t,1.4,1.6,1.9,2.1));
   if(t>.5&&t<3.6)p.caption='今天也一起加油吧。';
  }
  return p;
 }
}
