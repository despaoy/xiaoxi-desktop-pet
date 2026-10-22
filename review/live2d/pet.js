'use strict';
(async()=>{
 const status=document.getElementById('status');
 const subtitle=document.getElementById('subtitle');
 let bridge=null,focused=false,speechRemaining=0,speechPhase=0,mouth=0;
 let interaction='', interactionAge=0, preferences={}, captionText='';
 const report=name=>bridge?.event(name);
 try{
  if(window.qt && window.QWebChannel){
   bridge=await new Promise(resolve=>new QWebChannel(qt.webChannelTransport,c=>resolve(c.objects.pet)));
   bridge.stateChanged.connect(json=>{
    const data=JSON.parse(json);
    if('focused' in data)focused=!!data.focused;
    if(data.preferences)preferences=data.preferences;
    if(['greeting','blink','stretch','mouth','idle'].includes(data.interaction)){
     interaction=data.interaction;interactionAge=0;
     speechRemaining=(interaction==='mouth'||interaction==='greeting')?6000:0;speechPhase=0;
     bridge.actionStarted(interaction);
    }
    if(Number.isFinite(data.speechMs)&&!interaction){speechRemaining=Math.max(0,Math.min(8000,data.speechMs));speechPhase=0;}
   });
  }
  const app=new PIXI.Application({view:document.getElementById('canvas'),resizeTo:window,
   backgroundAlpha:0,antialias:true,autoDensity:true,resolution:Math.min(devicePixelRatio,2)});
  app.ticker.maxFPS=60;
  const requestedVersion=Number(new URLSearchParams(location.search).get('v'));
  const demoAction=new URLSearchParams(location.search).get('demo');
  const version=[19,20,21,22,23,24,25,26].includes(requestedVersion)?requestedVersion:19;
  const model=await PIXI.live2d.Live2DModel.from(`silver-v${version}-diagnostic/silver-dragon-v${version}.model3.json`,
   {autoUpdate:false,autoInteract:false});
  app.stage.addChild(model);model.anchor.set(.5,1);
  const width=model.width,height=model.height;
  const VX=50,VW=1014,VBOTTOM=1410,VH=1387;
  let baseScale=1;
  const fit=()=>{
   baseScale=Math.min(innerWidth/VW,innerHeight/VH);
   model.scale.set(baseScale);
   model.position.set((width/2-VX)*baseScale,innerHeight+(height-VBOTTOM)*baseScale);
  };
  addEventListener('resize',fit);fit();
  const core=model.internalModel.coreModel,idle=new SilverIdleMotion();
  let x=0,y=0,tx=0,ty=0,breath=0,eyeOpen=1,frames=0,appliedBreath=0,dragImpulse=0;
  const motion={angleX:0,angleY:0,angleZ:0,bodyX:0,bodyY:0,bodyZ:0,
   wingL:0,wingR:0,hairFront:0,hairSide:0,hairBack:0,brow:0,eyeSmile:0,mouthForm:0};
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const follow=(current,target,ms,tau)=>current+(target-current)*(1-Math.exp(-ms/tau));
  const setCaption=text=>{
   if(text===captionText)return;
   captionText=text;
   subtitle.textContent=text||'';
   subtitle.classList.toggle('visible',!!text);
  };
  const animationStarted=performance.now();
  if(['greeting','stretch','blink','mouth'].includes(demoAction)){
   interaction=demoAction;interactionAge=0;
   speechRemaining=(demoAction==='mouth'||demoAction==='greeting')?6000:0;
  }
  model.internalModel.on('beforeModelUpdate',()=>{
   core.setParameterValueById('ParamBreath',breath);
   core.setParameterValueById('ParamMouthOpenY',mouth);
   core.setParameterValueById('ParamMouthForm',motion.mouthForm);
   core.setParameterValueById('ParamEyeLOpen',eyeOpen);
   core.setParameterValueById('ParamEyeROpen',eyeOpen);
   core.setParameterValueById('ParamEyeLSmile',motion.eyeSmile);
   core.setParameterValueById('ParamEyeRSmile',motion.eyeSmile);
   core.setParameterValueById('ParamEyeBallX',x);
   core.setParameterValueById('ParamEyeBallY',y);
   core.setParameterValueById('ParamBrowLY',motion.brow);
   core.setParameterValueById('ParamBrowRY',motion.brow);
   core.setParameterValueById('ParamAngleX',motion.angleX);
   core.setParameterValueById('ParamAngleY',motion.angleY);
   core.setParameterValueById('ParamAngleZ',motion.angleZ);
   core.setParameterValueById('ParamBodyAngleX',motion.bodyX);
   core.setParameterValueById('ParamBodyAngleY',motion.bodyY);
   core.setParameterValueById('ParamBodyAngleZ',motion.bodyZ);
   if(version>=20){
    core.setParameterValueById('ParamWingL',motion.wingL);
    core.setParameterValueById('ParamWingR',motion.wingR);
   }
   if(version>=22){
    core.setParameterValueById('ParamHairFront',motion.hairFront);
    core.setParameterValueById('ParamHairSide',motion.hairSide);
    core.setParameterValueById('ParamHairBack',motion.hairBack);
    core.setParameterValueById('ParamHairSway',motion.hairSide);
   }
   appliedBreath=core.getParameterValueById('ParamBreath');
  });
  const updateCore=core.update.bind(core);
  let meshRestores=[];
  let currentInteractionPose=null;
  core.update=()=>{
   for(const [points,original] of meshRestores)points.set(original);
   meshRestores=[];
   updateCore();
   // The exported mouth/wing keys are deliberately subtle. Enlarge only the
   // explicit interaction's mesh, leaving the resting artwork untouched.
   if(interaction==='mouth'||interaction==='greeting'){
    const points=core.getDrawableVertices(core.getDrawableIndex('ArtMesh30'));
    meshRestores.push([points,points.slice()]);
    let cy=0;for(let i=1;i<points.length;i+=2)cy+=points[i];cy/=points.length/2;
    for(let i=1;i<points.length;i+=2)points[i]=cy+(points[i]-cy)*(1+3*mouth);
   }
   if(interaction==='stretch'||interaction==='greeting'){
    const wave=Math.sin(Math.PI*Math.min(1,interactionAge/6000))*Math.sin(2*Math.PI*interactionAge/3000);
    const lift=currentInteractionPose?Math.max(0,-currentInteractionPose.arm):0;
    for(const id of ['ArtMesh10','ArtMesh11']){
     const points=core.getDrawableVertices(core.getDrawableIndex(id));
     meshRestores.push([points,points.slice()]);
     const xs=Array.from(points).filter((_,i)=>i%2===0);
     const hinge=Math.abs(Math.min(...xs))<Math.abs(Math.max(...xs))?Math.min(...xs):Math.max(...xs);
     for(let i=0;i<points.length;i+=2){
      points[i]=hinge+(points[i]-hinge)*(1+.18*wave);
      points[i+1]-=14*lift;
     }
    }
   }
  };
  app.ticker.add(()=>{
   const ms=Math.min(app.ticker.elapsedMS,50);
   interactionAge+=ms;if(interactionAge>(interaction==='blink'?2400:6200))interaction='';
   const amp=(focused?.65:1)*(preferences.amplitude??1);
   const pose=idle.update(ms,{amplitude:amp,breathing:preferences.breathe!==false,blinking:preferences.blink!==false});
   const interactionPose=interaction?SilverInteractionMotion.pose(interaction,interactionAge):null;
   const p=interactionPose;
   dragImpulse*=Math.exp(-ms/240);
   const target={
    angleX:pose.headX+tx*3.2*amp,
    angleY:pose.headY+ty*2.2*amp,
    angleZ:pose.headZ+dragImpulse*.35,
    bodyX:pose.bodyX+tx*.65*amp,
    bodyY:pose.bodyY,
    bodyZ:pose.bodyZ+dragImpulse,
    wingL:preferences.wings===false?0:pose.wingL,
    wingR:preferences.wings===false?0:pose.wingR,
    hairFront:preferences.hair===false?0:pose.hairFront,
    hairSide:preferences.hair===false?0:pose.hairSide,
    hairBack:preferences.hair===false?0:pose.hairBack,
    brow:pose.brow,
    eyeSmile:pose.eyeSmile,
    mouthForm:pose.mouthForm
   };
   let targetMouth=speechRemaining>0?.90*Math.pow(Math.max(0,Math.sin(speechPhase/150)),.7)*Math.min(1,speechRemaining/180):(preferences.mouth===false?0:pose.idleMouth);
   let caption='';
   if(p){
    target.angleX+=p.angleX*amp;target.angleY+=p.angleY*amp;target.angleZ+=p.angleZ*amp;
    target.bodyX+=p.bodyX*amp;target.bodyY+=p.bodyY*amp;target.bodyZ+=p.bodyZ*amp;
    target.wingL+=(p.wing*amp);target.wingR+=(p.wing*amp);
    if(preferences.hair!==false){target.hairFront+=p.hair*amp;target.hairSide+=p.hair*amp;target.hairBack+=p.hair*amp;}
    target.brow+=p.brow*amp;target.eyeSmile=Math.max(target.eyeSmile,p.eyeSmile*amp);
    target.mouthForm+=p.mouthForm*amp;
    if(p.mouth>0)targetMouth=Math.max(targetMouth,p.mouth*amp);
    caption=p.caption;
   }
   // Small damped follow: the head leads, the body and hair trail it.
   motion.angleX=follow(motion.angleX,target.angleX,ms,95);
   motion.angleY=follow(motion.angleY,target.angleY,ms,115);
   motion.angleZ=follow(motion.angleZ,target.angleZ,ms,130);
   motion.bodyX=follow(motion.bodyX,target.bodyX,ms,220);
   motion.bodyY=follow(motion.bodyY,target.bodyY,ms,240);
   motion.bodyZ=follow(motion.bodyZ,target.bodyZ,ms,180);
   motion.wingL=follow(motion.wingL,target.wingL,ms,165);
   motion.wingR=follow(motion.wingR,target.wingR,ms,165);
   motion.hairFront=follow(motion.hairFront,target.hairFront,ms,100);
   motion.hairSide=follow(motion.hairSide,target.hairSide,ms,115);
   motion.hairBack=follow(motion.hairBack,target.hairBack,ms,130);
   motion.brow=follow(motion.brow,target.brow,ms,260);
   motion.eyeSmile=follow(motion.eyeSmile,target.eyeSmile,ms,180);
   motion.mouthForm=follow(motion.mouthForm,target.mouthForm,ms,180);
   speechRemaining=Math.max(0,speechRemaining-ms);speechPhase+=ms;
   mouth=follow(mouth,targetMouth,ms,45);
   breath=pose.breath;eyeOpen=pose.eyeOpen;
   if(p&&p.blink!==null&&p.blink!==undefined)eyeOpen=Math.min(eyeOpen,1-p.blink*amp);
   if(interaction==='blink'){
    const blinkAge=interactionAge<900?interactionAge-180:interactionAge-1080;
    eyeOpen=blinkAge>=0&&blinkAge<520 ? 1-Math.pow(Math.sin(Math.PI*blinkAge/520),.6):1;
   }
   x=follow(x,clamp(tx+pose.gazeX,-1,1),ms,85);
   y=follow(y,clamp(ty+pose.gazeY,-1,1),ms,110);
   setCaption(interaction?caption:'');
   status.textContent=interaction ? ({greeting:'向你打招呼',blink:'眨眨眼',stretch:'舒展翅膀',mouth:'嘴型演示',idle:'恢复待机'}[interaction]) : (bridge?'':'浏览器预览');
   model.rotation=0;
   model.scale.set(baseScale,baseScale);
   currentInteractionPose=interactionPose;
   model.update(ms);
   frames++;
   if(interaction && frames%3===0){
    const extent=(id,axis)=>{const a=Array.from(core.getDrawableVertices(core.getDrawableIndex(id))).filter((_,i)=>i%2===axis);return Math.max(...a)-Math.min(...a);};
    bridge?.interactionSample(interaction,extent('ArtMesh21',1),extent('ArtMesh10',0),extent('ArtMesh30',1));
   }
   if(frames%6===0){
    const vertices=core.getDrawableVertices(core.getDrawableIndex('ArtMesh30'));
    const ys=Array.from(vertices).filter((_,i)=>i%2);
    bridge?.mouthSample(mouth,Math.max(...ys)-Math.min(...ys));
   }
   if(frames%45===0)bridge?.sample(appliedBreath,frames,
    core.getDrawableVertices(core.getDrawableIndex('ArtMesh6'))[1]);
   if(frames%45===0){
    const width=id=>{const xs=Array.from(core.getDrawableVertices(core.getDrawableIndex(id))).filter((_,i)=>i%2===0);return Math.max(...xs)-Math.min(...xs);};
    bridge?.motionSample(performance.now()-animationStarted,frames,width('ArtMesh10'),width('ArtMesh11'));
   }
  });
  const canvas=app.view;let press=null;
  canvas.onpointerdown=e=>{
   if(e.button!==0)return;
   press={x:e.screenX,y:e.screenY,lastX:e.screenX,dragged:false};
   canvas.setPointerCapture(e.pointerId);bridge?.beginDrag();
  };
  canvas.onpointermove=e=>{
   if(press){
    const dx=e.screenX-press.x,dy=e.screenY-press.y;
    if(Math.abs(dx)+Math.abs(dy)>5)press.dragged=true;
    if(press.dragged){
     const step=e.screenX-(press.lastX??e.screenX);
     dragImpulse=clamp(dragImpulse+step*.12,-3.2,3.2);
     bridge?.drag(Math.round(dx),Math.round(dy));
    }
    press.lastX=e.screenX;
   }else{
    tx=clamp((e.clientX-innerWidth/2)/(innerWidth*.4),-1,1);
    ty=clamp((innerHeight*.35-e.clientY)/(innerHeight*.4),-1,1);
   }
  };
  canvas.onpointerup=e=>{
   if(!press)return;
   if(press.dragged){dragImpulse=0;bridge?.endDrag();}else report('click');
   press=null;canvas.releasePointerCapture(e.pointerId);
  };
  canvas.onpointercancel=()=>{if(press?.dragged)bridge?.endDrag();dragImpulse=0;press=null;};
  canvas.onpointerenter=()=>report('hover');
  canvas.onpointerleave=()=>{tx=ty=0;report('leave');};
  canvas.oncontextmenu=e=>{e.preventDefault();report('menu');};
  status.textContent=bridge?'':'浏览器预览 · 桌面功能需从桌宠启动';
  report('ready');
 }catch(error){
  const detail=error&&(error.stack||error.message)||String(error);
  status.textContent='形象加载失败，详情见错误窗口';
  bridge?.error(String(detail));console.error(error);
 }
})();
