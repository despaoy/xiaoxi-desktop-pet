'use strict';
// Pure timing logic shared by the preview and desktop host.
(function(root){
 class SilverIdleMotion {
  constructor(random=Math.random){
   this.random=random;this.time=0;this.amplitude=1;
   this.nextBlink=2600+this.random()*900;this.blinkStart=null;this.blinkCount=0;
  }
  update(ms,{breathing=true,amplitude=1,blinking=true,eyeOpen=1}={}){
   ms=Math.max(0,Math.min(ms,50));this.time+=ms;
   this.amplitude+=((breathing?amplitude:0)-this.amplitude)*(1-Math.exp(-ms/520));
   const t=this.time;
   const wave=(period,phase=0)=>Math.sin(t*Math.PI*2/period+phase);
   const breath=(1-Math.cos(t*Math.PI*2/4600))/2*this.amplitude;
   let openness=eyeOpen;
   if(!blinking){this.blinkStart=null;this.nextBlink=t+2800;}
   else {
    if(this.blinkStart===null&&t>=this.nextBlink){this.blinkStart=t;this.blinkCount++;}
    if(this.blinkStart!==null){
     const age=t-this.blinkStart;
     const smooth=x=>x*x*(3-2*x);
     if(age<90)openness=1-smooth(age/90);
     else if(age<125)openness=0;
     else if(age<285)openness=smooth((age-125)/160);
     else {
      this.blinkStart=null;
      // Occasional quick double-blink, otherwise a long quiet interval.
      this.nextBlink=t+(this.random()<.16?170:3200+this.random()*3000);
      openness=1;
     }
    } else openness=1;
   }
   // Long, quiet pauses between a small lip movement; not continuous talking.
   const lipAge=(t-3600)%11300;
   const idleMouth=t>=3600&&lipAge>=0&&lipAge<1600
    ? .70*Math.pow(Math.sin(Math.PI*lipAge/1600),2)*this.amplitude:0;
   // Low-frequency weight shift and head drift. Keep all values in model
   // parameter units (degrees for angles, normalised for hair/wings).
   const headX=(wave(8300,.2)*1.15+wave(13700,1.9)*.45)*this.amplitude;
   const headY=(wave(10100,1.4)*.75+wave(16300,.3)*.28)*this.amplitude;
   const headZ=(wave(11700,2.1)*.65+wave(7100,.7)*.25)*this.amplitude;
   const bodyX=wave(9700,.9)*.55*this.amplitude;
   const bodyY=wave(12100,2.4)*.22*this.amplitude;
   const sway=(wave(9700)*.0045+wave(15700)*.002)*this.amplitude;
   const bodyZ=sway*190;
   const hairFront=(wave(2600,.3)*.22+headX*.035)*this.amplitude;
   const hairSide=(wave(3200,1.1)*.25+headX*.045)*this.amplitude;
   const hairBack=(wave(4100,2.2)*.18+headX*.03)*this.amplitude;
   const wingL=(wave(3300,.2)*.20+wave(6900,1.7)*.05)*this.amplitude;
   const wingR=(wave(3300,.65)*.20+wave(6900,2.15)*.05)*this.amplitude;
   const gazeX=(wave(4300,.5)*.07+wave(2100,1.1)*.025)*this.amplitude;
   const gazeY=(wave(5100,1.8)*.05+wave(2800,.4)*.02)*this.amplitude;
   const brow=wave(7600,1.3)*.045*this.amplitude;
   const eyeSmile=.02+wave(10500,.8)*.015*this.amplitude;
   const mouthForm=wave(12300,1.6)*.05*this.amplitude;
   return {breath,eyeOpen:openness,blinkCount:this.blinkCount,idleMouth,sway,
    stretch:1+breath*.008,headX,headY,headZ,bodyX,bodyY,bodyZ,
    hairFront,hairSide,hairBack,wingL,wingR,gazeX,gazeY,brow,eyeSmile,mouthForm};
  }
 }
 if(typeof module!=='undefined'&&module.exports)module.exports=SilverIdleMotion;
 else root.SilverIdleMotion=SilverIdleMotion;
})(typeof window!=='undefined'?window:this);
