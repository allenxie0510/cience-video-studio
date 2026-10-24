#!/usr/bin/env node
// Calls ego-browser's supported page APIs. No npm dependencies or shell interpolation.
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve, join, delimiter } from 'node:path';
import { pathToFileURL } from 'node:url';
import { once } from 'node:events';

export async function render(taskSpace, opts) {
  const space = await taskSpace(opts.space);
  const page = space.page('p1');
  await page.goto(opts.url);
  await page.cdp('Emulation.setDeviceMetricsOverride', {width:opts.width,height:opts.height,deviceScaleFactor:1,mobile:false});
  await page.waitForFunction('window.__VIDEO__ && typeof window.__VIDEO__.setTime === "function"');
  await page.evaluate(async () => { await document.fonts.ready; });
  const nativeFrameExport = await page.evaluate(() => typeof window.__VIDEO__.getFramePNG === 'function');
  const full = await page.evaluate(() => window.__VIDEO__.duration);
  if (!Number.isFinite(full) || full <= 0) throw new Error('Invalid __VIDEO__.duration');
  const duration = Math.min(opts.seconds ?? full, full);
  if (opts.audio) {
    const measured = Number(execFileSync(opts.ffprobe,['-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',opts.audio],{encoding:'utf8'}).trim());
    if (!Number.isFinite(measured) || Math.abs(measured-duration) > .15) throw new Error(`Audio/page duration mismatch: ${measured} vs ${duration}`);
  }
  mkdirSync(dirname(opts.out),{recursive:true});
  const frames = Math.ceil(duration*opts.fps);
  const args=['-v','error','-nostdin','-n','-f','image2pipe','-vcodec','png','-framerate',String(opts.fps),'-i','pipe:0'];
  if(opts.audio) args.push('-i',opts.audio,'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k','-af',`apad=whole_dur=${frames/opts.fps}`);
  else args.push('-an');
  args.push('-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-t',String(frames/opts.fps),'-movflags','+faststart',opts.out);
  const ff = spawn(opts.ffmpeg,args,{stdio:['pipe','ignore','pipe']});
  let ffError='', streamError;
  ff.stderr.on('data',b=>{ffError+=b;});
  ff.stdin.on('error',e=>{streamError=e;});
  const complete = new Promise(ok=>{ff.on('error',e=>{streamError=e;ok(-1);});ff.on('close',code=>ok(code));});
  try {
    for(let i=0;i<frames;i++){
      if(streamError) throw streamError;
      await page.evaluate(async t=>{await window.__VIDEO__.setTime(t);const issues=window.__VIDEO__.auditLayout?.()||[];if(issues.length)throw Error(`Layout failed at ${t}: ${JSON.stringify(issues)}`);},i/opts.fps);
      let png;
      if(nativeFrameExport){
        const data=await page.evaluate(async()=>window.__VIDEO__.getFramePNG());
        if(typeof data!=='string') throw Error('getFramePNG must return a PNG base64 string');
        png=Buffer.from(data,'base64');
      }else{
        const dpr=await page.evaluate(()=>devicePixelRatio);
        const shot=await page.cdp('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:opts.width,height:opts.height,scale:1/dpr},captureBeyondViewport:false,fromSurface:true});
        png=Buffer.from(shot.data,'base64');
      }
      if(png.length<24||png.toString('hex',0,8)!=='89504e470d0a1a0a'||png.readUInt32BE(16)!==opts.width||png.readUInt32BE(20)!==opts.height)throw Error('PNG dimensions differ from requested output; inspect the stage and actual DPR');
      if(!ff.stdin.write(png)) await once(ff.stdin,'drain');
      if(i % (opts.fps*5)===0) console.log(`frame ${i}/${frames}`);
    }
    ff.stdin.end();
    const code = await complete;
    if(code !== 0) throw new Error(`ffmpeg exit ${code}: ${ffError}`);
    console.log(JSON.stringify({out:opts.out,seconds:frames/opts.fps,frames,audio:!!opts.audio,spaceId:space.spaceId}));
  } catch(e) { ff.stdin.destroy(); ff.kill('SIGTERM'); await complete.catch(()=>{}); throw e; }
}

if (process.argv[1] && import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
  const opts={width:1280,height:720,fps:30};
  const allowed=new Set(['url','out','space','width','height','fps','audio','seconds']);
  for(let i=2;i<process.argv.length;i+=2){
    const key=process.argv[i].replace(/^--/,'');
    if(!allowed.has(key)||process.argv[i+1]===undefined) throw new Error('Usage: render.mjs --url URL --out FILE --space ID [--width 1280 --height 720 --fps 30 --audio WAV --seconds 2]');
    opts[key]=['space','width','height','fps','seconds'].includes(key)?Number(process.argv[i+1]):process.argv[i+1];
  }
  if(!opts.url||!opts.out||!Number.isInteger(opts.space)||opts.space<=0) throw new Error('--url, --out and --space are required');
  for(const k of ['width','height','fps']) if(!Number.isInteger(opts[k])||opts[k]<=0) throw new Error(`Invalid ${k}`);
  if(opts.width%2||opts.height%2) throw new Error('H.264 width/height must be even');
  if(opts.seconds!==undefined&&(!Number.isFinite(opts.seconds)||opts.seconds<=0)) throw new Error('Invalid seconds');
  const parsed=new URL(opts.url);
  if(!['http:','https:','file:'].includes(parsed.protocol)) throw new Error('Unsupported URL');
  opts.out=resolve(opts.out);
  if(existsSync(opts.out)) throw new Error('Refusing to overwrite output');
  if(opts.audio) opts.audio=resolve(opts.audio);
  for(const name of ['ffmpeg','ffprobe']){
    opts[name]=(process.env.PATH||'').split(delimiter).map(p=>join(p,name)).find(p=>existsSync(p));
    if(!opts[name]) throw new Error(`${name} not found on PATH`);
  }
  const code=`const mod=await import(${JSON.stringify(import.meta.url)}); await mod.render(taskSpace,${JSON.stringify(opts)});`;
  const child=spawn('ego-browser',['nodejs','-e',code],{stdio:'inherit'});
  child.on('error',e=>{console.error(e.message);process.exitCode=1;});
  child.on('exit',code=>{process.exitCode=code??1;});
}
