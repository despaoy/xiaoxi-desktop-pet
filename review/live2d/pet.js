'use strict';
(async()=>{
 const status=document.getElementById('status');
 let bridge=null,focused=false,speechRemaining=0,speechPhase=0,mouth=0;
 let interaction='', interactionAge=0, preferences={};
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
  let x=0,y=0,tx=0,ty=0,breath=0,eyeOpen=1,frames=0,appliedBreath=0;
  const animationStarted=performance.now();
  model.internalModel.on('beforeModelUpdate',()=>{
   core.setParameterValueById('ParamBreath',breath);
   core.setParameterValueById('ParamMouthOpenY',mouth);
   core.setParameterValueById('ParamEyeLOpen',eyeOpen);
   core.setParameterValueById('ParamEyeROpen',eyeOpen);
   core.setParameterValueById('ParamEyeBallX',x);
   core.setParameterValueById('ParamEyeBallY',y);
   if(version>=20){
    const manualWing=interaction==='stretch'||interaction==='greeting';
    const stretch=manualWing ? -Math.sin(2*Math.PI*Math.min(1,interactionAge/3200)) : 0;
    core.setParameterValueById('ParamWingL',manualWing ? stretch : (preferences.wings===false?0:Math.sin(idle.time/1800)*.7));
    core.setParameterValueById('ParamWingR',manualWing ? stretch : (preferences.wings===false?0:Math.sin(idle.time/1800-.45)*.7));
   }
   if(version>=22)core.setParameterValueById('ParamHairSway',preferences.hair===false?0:Math.sin(idle.time/2100-.6)*.7);
   appliedBreath=core.getParameterValueById('ParamBreath');
  });
  const updateCore=core.update.bind(core);
  let meshRestores=[];
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
    for(const id of ['ArtMesh10','ArtMesh11']){
     const points=core.getDrawableVertices(core.getDrawableIndex(id));
     meshRestores.push([points,points.slice()]);
     const xs=Array.from(points).filter((_,i)=>i%2===0);
     const hinge=Math.abs(Math.min(...xs))<Math.abs(Math.max(...xs))?Math.min(...xs):Math.max(...xs);
     for(let i=0;i<points.length;i+=2)points[i]=hinge+(points[i]-hinge)*(1+.12*wave);
    }
   }
  };
  app.ticker.add(()=>{
   const ms=Math.min(app.ticker.elapsedMS,50);
   interactionAge+=ms;if(interactionAge>(interaction==='blink'?2400:6200))interaction='';
   status.textContent=interaction ? ({greeting:'向你打招呼',blink:'眨眨眼',stretch:'舒展翅膀',mouth:'嘴型演示',idle:'恢复待机'}[interaction]) : (bridge?'':'浏览器预览');
   const pose=idle.update(ms,{amplitude:(focused?.65:1)*(preferences.amplitude??1),breathing:preferences.breathe!==false,blinking:preferences.blink!==false});
   speechRemaining=Math.max(0,speechRemaining-ms);speechPhase+=ms;
   const syllable=Math.pow(Math.max(0,Math.sin(speechPhase/150)),.7);
   const targetMouth=speechRemaining>0?.90*syllable*Math.min(1,speechRemaining/180):(preferences.mouth===false?0:pose.idleMouth);
   mouth+=(targetMouth-mouth)*(1-Math.exp(-ms/45));
   breath=pose.breath;eyeOpen=pose.eyeOpen;
   if(interaction==='blink'){
    const blinkAge=interactionAge<900?interactionAge-180:interactionAge-1080;
    eyeOpen=blinkAge>=0&&blinkAge<520 ? 1-Math.pow(Math.sin(Math.PI*blinkAge/520),.6):1;
   }
   model.rotation=0;
   model.scale.set(baseScale,baseScale);
   const blend=1-Math.exp(-ms/100);x+=(tx-x)*blend;y+=(ty-y)*blend;
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
   press={x:e.screenX,y:e.screenY,dragged:false};
   canvas.setPointerCapture(e.pointerId);bridge?.beginDrag();
  };
  canvas.onpointermove=e=>{
   if(press){
    const dx=e.screenX-press.x,dy=e.screenY-press.y;
    if(Math.abs(dx)+Math.abs(dy)>5)press.dragged=true;
    if(press.dragged)bridge?.drag(Math.round(dx),Math.round(dy));
   }else{
    tx=Math.max(-1,Math.min(1,(e.clientX-innerWidth/2)/(innerWidth*.4)));
    ty=Math.max(-1,Math.min(1,(innerHeight*.35-e.clientY)/(innerHeight*.4)));
   }
  };
  canvas.onpointerup=e=>{
   if(!press)return;
   if(press.dragged)bridge?.endDrag();else report('click');
   press=null;canvas.releasePointerCapture(e.pointerId);
  };
  canvas.onpointercancel=()=>{if(press?.dragged)bridge?.endDrag();press=null;};
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
