import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const app = readFileSync(new URL("../script.js", import.meta.url), "utf8");
const read = name => readFileSync(new URL("../" + name, import.meta.url), "utf8");

function fixture(mode, payload, options = {}) {
  const elements = new Map();
  function el(key) {
    if (!elements.has(key)) {
      elements.set(key,{
        handlers:{}, dataset:{}, children:[], value:"", hidden:true, textContent:"",
        files:[{name:"file.png"}], src:"", href:"", attrs:{},
        setAttribute(name,value){this.attrs[name]=value;},
        addEventListener(name,callback){this.handlers[name]=callback;},
        pause(){this.paused=true;},
        removeAttribute(name){if(name==="src")this.src="";},
        load(){this.loaded=true;},
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
    fetch:async (url,requestOptions)=>{
      request={url,options:requestOptions};
      if (options.fetchImpl) return options.fetchImpl(url,requestOptions);
      return options.error
        ? {ok:false,status:options.error.status,json:async()=>({detail:options.error.detail})}
        : {ok:true,json:async()=>payload};
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


test("client rejects 9MB uploads before spending API credits", async()=>{
  const screen=fixture("photo",{traits:{},writing_style:{}});
  screen.el("#analysis-image").files=[{name:"oversize.png",size:9*1024*1024,type:"image/png"}];
  screen.el("#api-key").value="local-key";
  await screen.el("#photo-analysis-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.request(),undefined);
  assert.equal(screen.el("#status").dataset.error,"true");
  assert.equal(screen.el("#api-key").value,"local-key");
});

test("client rejects non-image uploads without contacting the server",async()=>{
  const screen=fixture("signature",{analysis:{}});
  screen.el("#analysis-image").files=[{name:"notes.pdf",size:32,type:"application/pdf"}];
  screen.el("#api-key").value="local-key";
  await screen.el("#signature-analysis-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.request(),undefined);
  assert.equal(screen.el("#status").dataset.error,"true");
});

test("client never saves the key after a successful request",async()=>{
  const screen=fixture("generate",{
    signature_png_url:"/signature.png",animation_mp4_url:"/signature.mp4"
  });
  screen.el("#portrait").files=[{name:"photo.png",size:512,type:"image/png"}];
  screen.el("#full-name").value="חגי און";
  screen.el("#api-key").value="sensitive-key";
  await screen.el("#signature-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.el("#api-key").value,"");
  assert.equal(screen.el("#results").hidden,false);
  assert.equal(screen.el("#signature-preview").src,"/signature.png");
  assert.equal(screen.el("#animation-preview").src,"/signature.mp4");
});


test("switching the photo clears stale results without extra requests",async()=>{
  const screen=fixture("photo",{
    summary:"חיוך",cues:["גבות"],vibe:"אנרגטי",
    traits:{joy:.8},writing_style:{pressure:.5}
  });
  screen.el("#api-key").value="temporary-key";
  await screen.el("#photo-analysis-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.el("#results").hidden,false);
  screen.el("#analysis-image").handlers.change();
  assert.equal(screen.el("#results").hidden,true);
  assert.equal(screen.el("#status").textContent,"");
});

test("changing name stops old video and clears its source",async()=>{
  const screen=fixture("generate",{
    signature_png_url:"/signature.png",animation_mp4_url:"/signature.mp4"
  });
  screen.el("#full-name").value="חגי און";
  screen.el("#api-key").value="temporary-key";
  await screen.el("#signature-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.el("#results").hidden,false);
  screen.el("#full-name").handlers.input();
  assert.equal(screen.el("#results").hidden,true);
  assert.equal(screen.el("#animation-preview").paused,true);
  assert.equal(screen.el("#animation-preview").src,"");
});

test("backend 422 name errors are translated and announced",async()=>{
  const screen=fixture("generate",{},{
    error:{status:422,detail:"Name is too long for a legible signature"}
  });
  screen.el("#full-name").value="Very Long Name";
  screen.el("#api-key").value="temporary-key";
  await screen.el("#signature-form").handlers.submit({preventDefault(){}});
  assert.match(screen.el("#status").textContent,/השם ארוך מדי/);
  assert.equal(screen.el("#status").attrs.role,"alert");
  assert.equal(screen.el("#status").attrs["aria-live"],"assertive");
  assert.equal(screen.el("#results").hidden,true);
  assert.equal(screen.el("#api-key").value,"");
});

test("asset links reject protocol-relative external URLs",async()=>{
  const screen=fixture("generate",{
    signature_png_url:"//attacker.example/unsafe.png",
    animation_mp4_url:"/signature.mp4"
  });
  screen.el("#full-name").value="חגי און";
  screen.el("#api-key").value="temporary-key";
  await screen.el("#signature-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.el("#results").hidden,true);
  assert.equal(screen.el("#status").dataset.error,"true");
});

test("shared interface has matching Hebrew and English keys and no duplicated cards",()=>{
  const css=read("style.css");
  assert.match(css,/\.metric-list\s*\{/);
  assert.match(css,/prefers-reduced-motion/);
  for(const file of ["index.html","analyze-photo.html","analyze-signature.html"]){
    const html=read(file);
    assert.equal((html.match(/data-i18n-aria-label="navLabel"/g)||[]).length,1);
    assert.equal((html.match(/class="page-shell"/g)||[]).length,1);
    assert.match(html,/aria-atomic="true"/);
  }
});


test("discard in-flight portrait analysis if the selected image changes",async()=>{
  let release;
  const response = new Promise(resolve => { release = resolve; });
  const screen=fixture("photo",{},{
    fetchImpl:()=>response
  });
  screen.el("#api-key").value="temporary-key";
  const submit=screen.el("#photo-analysis-form").handlers.submit({preventDefault(){}});
  assert.equal(screen.el("#photo-analysis-form").dataset.busy,"true");
  screen.el("#analysis-image").handlers.change();
  release({ok:true,json:async()=>({
    summary:"stale",cues:["stale"],vibe:"stale",
    traits:{joy:1},writing_style:{pressure:.7}
  })});
  await submit;
  assert.equal(screen.el("#results").hidden,true);
  assert.equal(screen.el("#status").textContent,"");
  assert.equal(screen.el("#photo-analysis-form").dataset.busy,"false");
});

test("do not submit twice or change analysis language while waiting",async()=>{
  let release;
  let calls=0;
  const wait=new Promise(resolve=>{release=resolve;});
  const screen=fixture("signature",{},{
    fetchImpl:()=>{calls++;return wait;}
  });
  screen.el("#api-key").value="temporary-key";
  const form=screen.el("#signature-analysis-form");
  const first=form.handlers.submit({preventDefault(){}});
  await form.handlers.submit({preventDefault(){}});
  assert.equal(calls,1);
  assert.equal(screen.el("#language-toggle").disabled,true);
  release({ok:true,json:async()=>({
    analysis:{description:"Observed line",impression:"Playful",
              features:{legibility:"Moderate"}}
  })});
  await first;
  assert.equal(screen.el("#language-toggle").disabled,false);
  assert.equal(screen.el("#results").hidden,false);
});
