'use strict';
// Local-only action and subtitle policy. Pure timing makes interruptions testable.
(function(root){
 const DURATIONS={greeting:5200,blink:2000,stretch:5600,mouth:4600,look:4800,relax:5000};
 const DEFAULT_LINES={
  greeting:['嗨，我在呢。','见到你真好。','今天也一起加油吧。'],
  blink:['眨眨眼，放松一下。','我有在认真看哦。','眼睛也歇一小会儿。'],
  stretch:['舒展一下翅膀。','伸个懒腰，慢慢来。','活动一下，轻松一点。'],
  mouth:['我在这里陪你。','按你的节奏来就好。','今天也一起加油吧。'],
  look:['看看这边，再看看那边。','我就在这里。','今天也不慌不忙。'],
  relax:['轻轻松松，晃一晃。','慢慢来就好。','休息一小会儿。']
 };
 class SilverBehaviorController {
  constructor({random=Math.random,onStart=()=>{}}={}){
   this.random=random;this.onStart=onStart;this.time=0;this.current=null;
   this.outgoing=null;this.pending=null;this.nextAuto=this.delay(8000,14000);
   this.lastAction='';this.lastStarts={};this.lastLines={};this.lastCaption=-Infinity;
   this.caption=null;this.blocked=false;
   this.context={visible:true,focused:false,dnd:false,speechEnabled:true,
    notificationBusy:false,editing:false,interacting:false,preferences:{},actionLines:{}};
  }
  delay(min,max){return min+this.random()*(max-min);}
  setContext(values){
   Object.assign(this.context,values);
   if(!this.canSpeak())this.caption=null;
   if(!this.context.visible){this.pending=null;this.stop();}
   if(!this.canAuto()&&this.current?.source==='auto')this.stop();
  }
  canAuto(){const c=this.context;return c.visible&&!c.focused&&!c.dnd&&
   !c.notificationBusy&&!c.editing&&!c.interacting&&c.preferences.actions!==false;}
  canSpeak(){const c=this.context;return c.visible&&!c.dnd&&c.speechEnabled&&
   !c.notificationBusy&&!c.editing&&!c.focused&&!c.interacting;}
  stop(){
   if(this.current)this.outgoing={...this.current,remaining:320};
   this.current=null;this.caption=null;this.nextAuto=this.time+this.delay(18000,32000);
  }
  request(action){
   if(action==='idle'){
    this.pending=null;this.stop();this.onStart('idle','manual');return true;
   }
   if(!Object.hasOwn(DURATIONS,action))return false;
   // Rapid repeated clicks neither restart a pose nor build a stale queue.
   if(this.current?.action===action||this.pending===action)return false;
   if(this.current?.source==='manual'){this.pending=action;return true;}
   if(this.current)this.stop();
   this.start(action,'manual');return true;
  }
  start(action,source){
   this.current={action,source,age:0};this.lastAction=action;this.lastStarts[action]=this.time;
   this.nextAuto=this.time+DURATIONS[action]+this.delay(18000,32000);
   this.caption=null;
   const cooldown=source==='auto'?45000:1800;
   if(this.canSpeak()&&this.time-this.lastCaption>=cooldown){
    const supplied=this.context.actionLines[action];
    const lines=Array.isArray(supplied)?supplied.filter(x=>typeof x==='string'&&x.trim()):DEFAULT_LINES[action];
    if(lines?.length){
     const candidates=lines.filter(x=>x!==this.lastLines[action]);
     const choices=candidates.length?candidates:lines;
     const text=choices[Math.min(choices.length-1,Math.floor(this.random()*choices.length))];
     this.lastLines[action]=text;this.lastCaption=this.time;
     this.caption={text,starts:this.time+250,ends:this.time+Math.min(4800,Math.max(2800,text.length*170))};
    }
   }
   this.onStart(action,source);
  }
  update(elapsed){
   // A suspended/hidden renderer must not catch up by firing many actions.
   const ms=Number.isFinite(elapsed)?Math.max(0,Math.min(elapsed,50)):0;
   this.time+=ms;
   if(this.outgoing){this.outgoing.age+=ms;this.outgoing.remaining-=ms;if(this.outgoing.remaining<=0)this.outgoing=null;}
   if(this.current){
    this.current.age+=ms;
    if(this.current.age>=DURATIONS[this.current.action]){
     this.current=null;
     if(this.pending){const next=this.pending;this.pending=null;this.start(next,'manual');}
    }
   }
   const allowed=this.canAuto();
   if(!allowed){this.blocked=true;this.nextAuto=this.time+this.delay(8000,14000);}
   else if(this.blocked){this.blocked=false;this.nextAuto=this.time+this.delay(8000,14000);}
   if(allowed&&!this.current&&!this.outgoing&&this.time>=this.nextAuto){
    const prefs=this.context.preferences;
    const choices=['look','relax',...(prefs.blink===false?[]:['blink']),...(prefs.wings===false?[]:['stretch'])]
     .filter(action=>action!==this.lastAction&&this.time-(this.lastStarts[action]??-Infinity)>=45000);
    if(choices.length)this.start(choices[Math.min(choices.length-1,Math.floor(this.random()*choices.length))],'auto');
    else this.nextAuto=this.time+this.delay(8000,14000);
   }
   if(this.caption&&(!this.canSpeak()||this.time>=this.caption.ends))this.caption=null;
   return {current:this.current,outgoing:this.outgoing,
    caption:this.caption&&this.time>=this.caption.starts?this.caption.text:''};
  }
 }
 SilverBehaviorController.DURATIONS=DURATIONS;
 SilverBehaviorController.DEFAULT_LINES=DEFAULT_LINES;
 if(typeof module!=='undefined'&&module.exports)module.exports=SilverBehaviorController;
 else root.SilverBehaviorController=SilverBehaviorController;
})(typeof window!=='undefined'?window:this);
