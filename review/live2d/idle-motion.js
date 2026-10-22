'use strict';
// Pure timing logic shared by the preview and desktop host.
(function(root){
 class SilverIdleMotion {
  constructor(random=Math.random){this.random=random;this.time=0;this.amplitude=1;this.nextBlink=2800;this.blinkStart=null;this.blinkCount=0;}
  update(ms,{breathing=true,amplitude=1,blinking=true,eyeOpen=1}={}){
   ms=Math.max(0,Math.min(ms,50));this.time+=ms;
   this.amplitude+=((breathing?amplitude:0)-this.amplitude)*(1-Math.exp(-ms/450));
   const breath=(1-Math.cos(this.time*Math.PI*2/4200))/2*this.amplitude;
   let openness=eyeOpen;
   if(!blinking){this.blinkStart=null;this.nextBlink=this.time+2800;}
   else {
    if(this.blinkStart===null&&this.time>=this.nextBlink){this.blinkStart=this.time;this.blinkCount++;}
    if(this.blinkStart!==null){
     const age=this.time-this.blinkStart;
     const smooth=t=>t*t*(3-2*t);
     if(age<90)openness=1-smooth(age/90);
     else if(age<125)openness=0;
     else if(age<285)openness=smooth((age-125)/160);
     else {this.blinkStart=null;this.nextBlink=this.time+3200+this.random()*2800;openness=1;}
    } else openness=1;
   }
   // Long, quiet pauses between a small lip movement; not continuous talking.
   const lipAge=(this.time-3600)%11300;
   const idleMouth=this.time>=3600&&lipAge>=0&&lipAge<1600
    ? .70*Math.pow(Math.sin(Math.PI*lipAge/1600),2)*this.amplitude:0;
   const sway=(Math.sin(this.time*Math.PI*2/9700)*.0045+
    Math.sin(this.time*Math.PI*2/15700)*.002)*this.amplitude;
   return {breath,eyeOpen:openness,blinkCount:this.blinkCount,idleMouth,sway,
    stretch:1+breath*.008};
  }
 }
 if(typeof module!=='undefined'&&module.exports)module.exports=SilverIdleMotion;
 else root.SilverIdleMotion=SilverIdleMotion;
})(typeof window!=='undefined'?window:this);
