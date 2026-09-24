import { readFileSync } from 'fs';
const html = readFileSync('training_english.html','utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
let code = m[1];
const elements = {};
const mkEl = () => ({ innerHTML:'', classList:{toggle(){},add(){},remove(){}}, style:{} });
global.document = {
  getElementById: (id)=>{ if(!elements[id]) elements[id]=mkEl(); return elements[id]; },
  querySelectorAll: ()=>[],
  querySelector: ()=>null,
  body: mkEl(),
};
global.window = global;
global.alert = ()=>{};
global.speechSynthesis = { cancel(){}, speak(){}, getVoices:()=>[] };
global.SpeechSynthesisUtterance = class { constructor(){} };
global.scrollTo = ()=>{};
eval(code);
const main = elements['main'];
console.log('main.innerHTML length:', main.innerHTML.length);
console.log('blocks rendered:', (main.innerHTML.match(/class="block"/g)||[]).length);
console.log('sentences rendered:', (main.innerHTML.match(/class="sent"/g)||[]).length);
console.log('cn divs:', (main.innerHTML.match(/译：/g)||[]).length);
console.log('xy divs:', (main.innerHTML.match(/class="xy"/g)||[]).length);
const toc = elements['toc'];
console.log('toc links:', (toc.innerHTML.match(/<a /g)||[]).length);
const firstBlock = main.innerHTML.slice(0, 500);
console.log('--- first 500 chars ---');
console.log(firstBlock);
