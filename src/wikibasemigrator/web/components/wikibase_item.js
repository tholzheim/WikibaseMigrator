export default {
  template: `
  <div class="container flex flex-col gap-2 mx-auto">
  <h2 class="flex flex-row text-2xl">
    <div v-html="getItemLink(entity.s_id, s_wikibase)"></div>
    <template v-if="entity.t_id == null">→ CREATE new Item</template>
    <template v-else>→ <div v-html="getItemLink(entity.t_id, t_wikibase)"></div></template>
  </h2>
  <div class="container mx-auto rounded-md bg-slate-300 p-2">
    <div class="grid grid-cols-3 gap-2">
      <div class="flex flex-col rounded-md bg-slate-200">
          <p>Label:</p>
          <div class="flex flex-row gap-2">
              <template v-for="lang in Object.keys(entity.labels)"> <div v-html="getLanguageStrng(entity.labels[lang], lang)"></div></template>
          </div>
      </div>
      <div class="flex flex-col rounded-md bg-slate-200">
          <p>Descriptions:</p>
          <div class="flex flex-row gap-2">
              <template v-for="lang in Object.keys(entity.descriptions)"> <div v-html="getLanguageStrng(entity.descriptions[lang], lang)"></div></template>
          </div>
      </div>
      <div class="flex flex-col rounded-md bg-slate-200">
          <p>Aliases:</p>
          <div class="flex flex-row gap-2">
            <template v-for="lang in Object.keys(entity.aliases)">
                <template v-for="alias in entity.aliases[lang]"> 
                    <div v-html="getLanguageStrng(alias, lang)"></div>
                </template>
            </template>
          </div>
      </div>
    </div>
      
  </div>
  <div v-for="claim in entity.claims">
     <div class="container mx-auto rounded-md bg-slate-300 p-2">
        <div class="flex flex-row gap-4">
           <div v-html="getItemLinkMapping(claim.s_id, claim.t_id)"</div>
           <div class="flex flex-col m-1 gap-2 grow">
              <div v-for="snak in claim.snaks">
                 <div class="container flex flex-col gap-1 p-2 rounded-md bg-slate-200 rounded grow"> 
                    <div v-html="renderSnak(snak.mainsnak)"
                 </div>
                 <div class="ml-10 bg-slate-100 rounded m-1 p-1">
                    <p>Qualifier:</p>
                    <div class="flex flex-col gap-1">
                       <div v-for="qualifier in snak.qualifiers" class="grid grid-cols-2  gap-5 px-1  rounded ring-1 m-1 ">
                          <div v-html="getItemLinkMapping(qualifier.s_id, qualifier.t_id)" class="flex flex-row"></div>
                          <div class="flex flex-col gap-1 grow">
                             <div v-for="snak in qualifier.snaks">
                                <div v-html="renderSnak(snak)"></div>
                             </div>
                          </div>
                       </div>
                    </div>
                 </div>
                 <div class="flex flex-col gap-2 ml-10 m-1 p-1  rounded bg-slate-100">
                    <div class="">References:</div>
                    <div v-for="reference_block in snak.references" >
                       <div class="m-1100 rounded ring-1 p-1">
                          <div v-for="reference in reference_block.reference" class="grid grid-cols-2  gap-5 px-1 bg-slate-50 m-1 rounded ring-1 ">
                             <div v-html="getItemLinkMapping(reference.s_id, reference.t_id)" class="flex flex-row"></div>
                             <div class="flex flex-col gap-2 grow">
                                <div v-for="snak in reference.snaks">
                                   <div v-html="renderSnak(snak)"></div>
                                </div>
                             </div>
                          </div>
                       </div>
                    </div>
                 </div>
              </div>
           </div>
        </div>
     </div>
  </div>
  </div>
  </div>
</div>
  `,
  data() {
    return {
      value: 0,
      css_classes_link:"underline text-blue-600 hover:text-blue-800 visited:text-purple-600"
    };
  },
  methods: {
    getSourceLabel(id) {
      return this.source_labels[id] || "no label"
    },
    getTargetLabel(id) {
      return this.target_labels[id] || "no label"
    },
    getLanguageStrng(str, lang){
      return `"${str}"@${lang}`
    },
    renderSnak(snak){
      if (snak.snaktype !== "value"){
        return `<div> ${snak.value} ${this.getItemLink("(build-in type)", "https://www.mediawiki.org/wiki/Wikibase/DataModel#Snaks")}</div`
      }
      switch (snak.type) {
        case "wikibase-item":
          return this.getItemLinkMapping(snak.value, snak.target_value)
        case "monolingualtext":
          return this.getLanguageStrng(snak.value, snak.language)
        default:
          return `<div> "${snak.value}"</div`
      }
    },
    getItemLink(item, location){
      return `<a href="${location}${item}" class="${this.css_classes_link}">${item}</a>`
    },
    getItemLinkMapping(s_id, t_id){
      if(t_id == null){
        return `
            <a href="${this.s_wikibase}${s_id}" class="${this.css_classes_link}">${s_id} (${ this.getSourceLabel(s_id) })</a>
            →
            <div class="text-red">MISSING</div>
        `
      }else{
          return `
            <a href="${this.s_wikibase}${s_id}" class="${this.css_classes_link}">${s_id} (${this.getSourceLabel(s_id)})</a>
            →
            <a href="${this.t_wikibase}${t_id}" class="${this.css_classes_link}">${t_id} (${this.getTargetLabel(t_id)})</a>
        `
        }
    },
  },
  props: {
    s_wikibase: URL,
    t_wikibase: URL,
    source_labels: Object,
    target_labels: Object,
    entity: Object,
    css_classes_link: String
  },
};