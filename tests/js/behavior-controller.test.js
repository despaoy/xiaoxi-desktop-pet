'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Controller=require('../../review/live2d/behavior-controller.js');
const Pose=require('../../review/live2d/interaction-motion.js');
const Idle=require('../../review/live2d/idle-motion.js');
const advance=(controller,ms)=>{let state;for(let n=0;n<ms;n+=50)state=controller.update(Math.min(50,ms-n));return state;};

test('repeated clicks do not rewind, and only the newest different manual action is queued',()=>{
 const starts=[],c=new Controller({random:()=>0,onStart:(a,s)=>starts.push([a,s])});
 assert.equal(c.request('greeting'),true);advance(c,800);
 assert.equal(c.request('greeting'),false);assert.equal(c.current.age,800);
 c.request('stretch');c.request('blink');
 assert.equal(c.pending,'blink');assert.equal(c.current.action,'greeting');
 advance(c,4400);assert.equal(c.current.action,'blink');assert.equal(c.pending,null);
 assert.deepEqual(starts,[['greeting','manual'],['blink','manual']]);
});

test('idle clears queued work and smoothly releases the active pose',()=>{
 const c=new Controller({random:()=>0});c.request('stretch');advance(c,1100);c.request('greeting');
 c.request('idle');assert.equal(c.current,null);assert.equal(c.pending,null);
 assert.equal(c.outgoing.action,'stretch');assert.equal(c.caption,null);
 advance(c,350);assert.equal(c.outgoing,null);assert.equal(c.current,null);
});

test('manual actions take priority over automatic ones without abrupt release',()=>{
 const c=new Controller({random:()=>0});advance(c,9000);
 assert.equal(c.current.source,'auto');c.request('greeting');
 assert.equal(c.current.source,'manual');assert.equal(c.current.action,'greeting');
 assert.equal(c.outgoing.action,'look');advance(c,350);assert.equal(c.outgoing,null);
});

test('automatic actions vary, rest between actions, and have per-action cooldowns',()=>{
 let seed=17;const random=()=>((seed=seed*16807%2147483647)-1)/2147483646;
 const starts=[],c=new Controller({random,onStart:(action,source)=>starts.push({action,source,at:c.time})});
 advance(c,360000);assert.ok(starts.length>=8);
 const last={};for(let i=0;i<starts.length;i++){
  const entry=starts[i];assert.equal(entry.source,'auto');
  if(i){assert.notEqual(entry.action,starts[i-1].action);
   assert.ok(entry.at-starts[i-1].at>=Controller.DURATIONS[starts[i-1].action]+18000);}
  if(last[entry.action])assert.ok(entry.at-last[entry.action]>=45000);
  last[entry.action]=entry.at;
 }
 assert.ok(new Set(starts.map(x=>x.action)).size>=3);
});

for(const [key,value] of Object.entries({focused:true,dnd:true,visible:false,notificationBusy:true,editing:true,interacting:true})){
 test(`${key} pauses automatic actions, without a catch-up burst`,()=>{
  const c=new Controller({random:()=>0});c.setContext({[key]:value});advance(c,60000);
  assert.equal(c.current,null);assert.equal(c.caption,null);
  c.setContext({[key]:!value});advance(c,5000);assert.equal(c.current,null);
  advance(c,4000);assert.equal(c.current.source,'auto');
 });
}

test('automatic action and component switches leave manual actions available',()=>{
 const starts=[],c=new Controller({random:()=>.8,onStart:a=>starts.push(a)});
 c.setContext({preferences:{actions:false}});advance(c,60000);assert.deepEqual(starts,[]);
 assert.equal(c.request('stretch'),true);assert.equal(c.current.action,'stretch');
 c.request('idle');c.setContext({preferences:{blink:false,wings:false}});advance(c,180000);
 assert.ok(starts.includes('look'));assert.ok(starts.includes('relax'));
 assert.equal(starts.filter(x=>x==='stretch').length,1);assert.ok(!starts.includes('blink'));
});

test('bubble policy respects speech switch, DND, input, focus, and notification priority',()=>{
 for(const context of [{speechEnabled:false},{dnd:true},{editing:true},{focused:true},{notificationBusy:true},{interacting:true}]){
  const c=new Controller({random:()=>0});c.setContext(context);c.request('greeting');
  assert.equal(advance(c,600).caption,'');assert.equal(c.current.action,'greeting');
 }
 const c=new Controller({random:()=>0});c.request('greeting');assert.ok(advance(c,300).caption);
 c.setContext({notificationBusy:true});assert.equal(c.caption,null);
 c.setContext({notificationBusy:false});assert.equal(advance(c,100).caption,'');
});

test('dragging clears an active manual caption without replaying it afterward',()=>{
 const c=new Controller({random:()=>0});c.request('greeting');
 assert.ok(advance(c,300).caption);
 c.setContext({interacting:true});assert.equal(c.caption,null);
 assert.equal(c.current.action,'greeting');
 c.setContext({interacting:false});assert.equal(advance(c,100).caption,'');
});

test('short captions avoid repetitions, expire, and do not form a backlog',()=>{
 const c=new Controller({random:()=>0});c.request('greeting');
 const first=advance(c,300).caption;assert.ok(first);
 assert.equal(advance(c,4900).caption,'');c.request('greeting');
 assert.notEqual(advance(c,300).caption,first);
 c.setContext({editing:true});advance(c,1000);c.setContext({editing:false});
 assert.equal(advance(c,500).caption,'');
});

test('custom action captions work, while old language packs use bundled fallbacks',()=>{
 const c=new Controller({random:()=>0});c.setContext({actionLines:{greeting:['自定义短句。']}});
 c.request('greeting');assert.equal(advance(c,300).caption,'自定义短句。');
 c.request('idle');advance(c,2000);c.request('blink');assert.ok(advance(c,300).caption);
 const language=JSON.parse(fs.readFileSync(path.join(__dirname,'../../assets/language/zh-CN.json'),'utf8'));
 assert.deepEqual(language.actions,Controller.DEFAULT_LINES);
});

test('auto bubble cooldown is global and at least 45 seconds',()=>{
 const c=new Controller({random:()=>0});let last=null,previous='',count=0;
 for(let i=0;i<6000;i++){
  const {caption}=c.update(50);
  if(caption&&!previous){if(last!==null)assert.ok(c.time-last>=45000);last=c.time;count++;}
  previous=caption;
 }
 assert.ok(count>=3);
});

test('unknown actions and suspended frames do not disturb animation state',()=>{
 const c=new Controller({random:()=>0});c.request('greeting');advance(c,100);
 assert.equal(c.request('not-an-action'),false);c.update(60000);assert.equal(c.current.age,150);
 c.update(NaN);assert.equal(c.current.age,150);c.update(-500);assert.equal(c.current.age,150);
});

test('all authored actions have finite bounded poses and return to neutral',()=>{
 for(const [action,duration] of Object.entries(Controller.DURATIONS)){
  for(let ms=0;ms<=duration;ms+=25){
   const pose=Pose.pose(action,ms);
   for(const [key,value] of Object.entries(pose))if(typeof value==='number'){
    assert.ok(Number.isFinite(value),`${action}:${key}:${ms}`);
    assert.ok(Math.abs(value)<4,`${action}:${key}:${ms}`);
   }
  }
  for(const [key,value] of Object.entries(Pose.pose(action,duration))){
   if(typeof value==='number')assert.ok(Math.abs(value)<1e-8,`${action}:${key} must settle`);
  }
 }
});

test('idle mouth movements are subtle, separated by quiet intervals, and breathing stays finite',()=>{
 const idle=new Idle(()=>.5);let peaks=0,active=false;
 for(let i=0;i<2400;i++){
  const pose=idle.update(50);
  assert.ok(pose.idleMouth>=0&&pose.idleMouth<=.24);assert.ok(Number.isFinite(pose.breath));
  if(pose.idleMouth>0&&!active)peaks++;active=pose.idleMouth>0;
 }
 assert.ok(peaks>=3&&peaks<=5);
});


test('disabling breathing does not silently disable wings, hair, or gaze',()=>{
 const idle=new Idle(()=>.5);let pose;
 for(let i=0;i<200;i++)pose=idle.update(50,{breathing:false});
 assert.ok(pose.breath<1e-6);assert.ok(Math.abs(pose.wingL)>.01);
 assert.ok(Math.abs(pose.hairSide)>.01);assert.ok(Math.abs(pose.gazeX)>.01);
});

test('renderer bridge runs the shipped controller, settings, and motion wiring together',async()=>{
 const vm=require('node:vm');let callback,tick,beforeUpdate;
 const elements={status:{textContent:''},subtitle:{textContent:'',classList:{toggle(){}}},
  canvas:{setPointerCapture(){},releasePointerCapture(){}}};
 const parameters={},started=[],events=[],reportedErrors=[];
 const core={setParameterValueById:(key,value)=>{parameters[key]=value;},
  getParameterValueById:key=>parameters[key]||0,getDrawableIndex:id=>id,
  getDrawableVertices:()=>new Float32Array([-1,-1,1,-1,1,1,-1,1]),update(){}};
 const model={width:1086,height:1448,anchor:{set(){}},scale:{set(){}},position:{set(){}},
  internalModel:{coreModel:core,on:(_,fn)=>{beforeUpdate=fn;}},
  update(){beforeUpdate();core.update();}};
 const context={console,URLSearchParams,performance:{now:()=>0},devicePixelRatio:1,
  innerWidth:182,innerHeight:249,location:{search:'?v=26'},addEventListener(){},
  document:{hidden:false,getElementById:id=>elements[id]},
  SilverIdleMotion:Idle,SilverInteractionMotion:Pose,SilverBehaviorController:Controller,
  qt:{webChannelTransport:{}},QWebChannel:function(_,ready){ready({objects:{pet:{
   stateChanged:{connect(fn){callback=fn;}},event:name=>events.push(name),
   actionStarted:action=>started.push(action),error:error=>reportedErrors.push(error),
   sample(){},mouthSample(){},motionSample(){},interactionSample(){},beginDrag(){},drag(){},endDrag(){}
  }}});},
  PIXI:{Application:function(){this.view=elements.canvas;this.stage={addChild(){}};
    this.ticker={elapsedMS:50,add(fn){tick=fn;}};},
   live2d:{Live2DModel:{from:async()=>model}}}};
 context.window=context;
 await vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../review/live2d/pet.js'),'utf8'),context);
 assert.ok(events.includes('ready'));assert.deepEqual(reportedErrors,[]);
 const state=values=>callback(JSON.stringify(values));const frames=count=>{for(let i=0;i<count;i++)tick();};
 state({preferences:{actions:false},interaction:'greeting'});frames(20);
 assert.ok(elements.subtitle.textContent);assert.equal(started.at(-1),'greeting');
 assert.ok(parameters.ParamMouthOpenY>0);
 state({interaction:'greeting'});frames(2);assert.equal(started.length,1);
 state({interaction:'look'});state({interaction:'relax'});frames(100);
 assert.equal(started.at(-1),'relax');assert.ok(!started.includes('look'));
 state({notificationBusy:true,speechMs:2500});frames(5);assert.equal(elements.subtitle.textContent,'');
 state({interaction:'idle',notificationBusy:false,dnd:true});frames(10);
 state({interaction:'look'});frames(20);assert.equal(elements.subtitle.textContent,'');
 assert.ok(Math.abs(parameters.ParamEyeBallX)>.1);
 for(const value of Object.values(parameters))assert.ok(Number.isFinite(value));
 assert.deepEqual(reportedErrors,[]);
});
