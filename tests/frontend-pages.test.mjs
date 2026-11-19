import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const app = readFileSync(new URL("../script.js", import.meta.url), "utf8");
const read = name => readFileSync(new URL("../" + name, import.meta.url), "utf8");

function fixture(mode, payload) {
  const elements = new Map();
  function el(key) {
    if (!elements.has(key)) {
      elements.set(key,{
        handlers:{}, dataset:{}, children:[], value:"", hidden:true, textContent:"",
        files:[{name:"file.png"}], src:"", href:"", attrs:{},
        setAttribute(name,value){this.attrs[name]=value;},
        addEventListener(name,callback){this.handlers[name]=callback;},
        replaceChildren(){this.children=[];},
        append(...children){this.children.push(...children);}
      });
    }
    return elements.get(key);
  }
  const root={lang:"",dir:""};
  let request;
  const context={
    document:{
      body:{dataset:{page:mode}}, documentElement:root,
      querySelector:el,querySelectorAll:()=>[],
      createElement:tag=>({tag,textContent:""})
    },
    FormData:class{values=new Map();set(key,value){this.values.set(key,value);}},
    fetch:async (url,options)=>{
      request={url,options};
      return {ok:true,json:async()=>payload};
    }
  };
  vm.runInNewContext(app,context);
  return {el,root,request:()=>request};
}

test("all pages use one CSS and JS shell with minimal duplicated structure",()=>{
  const css=read("style.css");
  assert.match(css, /:root\s*\{/);
  assert.match(css, /--color-primary:/);
  assert.match(css, /--space-4:/);
  assert.match(css, /\.button\s*\{/);
  for (const file of ["index.html","analyze-photo.html","analyze-signature.html"]) {
    const html=read(file);
    assert.match(html, /class="page-shell"/);
    assert.match(html, /href="\/style\.css"/);
    assert.match(html, /src="\/script\.js"/);
    assert.equal((html.match(/class="topbar"/g)||[]).length,1);
    assert.equal((html.match(/class="site-nav"/g)||[]).length,1);
  }
});

test("portrait analysis uploads photo and shows model scores and stroke effects",async()=>{
  const screen=fixture("photo",{
    summary:"חיוך גלוי ומבט ישיר",
    cues:["זוויות פה מורמות","ראש מוטה קלות"],
    vibe:"דמות נעימה ושובבה",
    traits:{joy:.9,tension:.1},
    writing_style:{pressure:.65,roundness:.8}
  });
  screen.el("#api-key").value="user-key";
  await screen.el("#photo-analysis-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.request().url,"/api/analyze-photo");
  assert.equal(screen.request().options.body.values.get("language"),"he");
  assert.equal(screen.el("#results").hidden,false);
  assert.equal(screen.el("#analysis-details").children.length,4);
  assert.equal(screen.el("#writing-details").children.length,4);
  assert.match(screen.el("#analysis-description").textContent,/זוויות פה מורמות/);
  assert.match(screen.el("#analysis-description").textContent,/דמות נעימה ושובבה/);
  assert.equal(screen.el("#api-key").value,"");
});

test("signature analysis displays descriptive interpretation instead of numeric data",async()=>{
  const screen=fixture("signature",{analysis:{
    description:"Curved handwriting",impression:"Playful",
    features:{flourish:"Long",legibility:"Fair"}
  }});
  screen.el("#api-key").value="user-key";
  screen.el("#language-toggle").handlers.click();
  await screen.el("#signature-analysis-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.request().url,"/api/analyze-signature");
  assert.equal(screen.request().options.body.values.get("language"),"en");
  assert.equal(screen.el("#results").hidden,false);
  assert.match(screen.el("#analysis-description").textContent,/Playful/);
  assert.equal(screen.el("#analysis-details").children.length,4);
  assert.equal(screen.el("#api-key").value,"");
});
