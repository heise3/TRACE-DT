args <- commandArgs(trailingOnly=TRUE)
setwd(args[1])
source('base_r_compat.R')
source_without_dplyr('rbo/low.R')
source_without_dplyr('rbo/hig.R')
options(digits=17)
# Validate published boundary-order algorithms against exhaustive legal permutations.
perms <- function(x) {
  if(length(x)<=1) return(list(x))
  unlist(lapply(seq_along(x),function(i) lapply(perms(x[-i]),function(z)c(x[i],z))),recursive=FALSE)
}
orders <- function(blocks) {
  ans <- list(character())
  for(b in blocks) ans <- unlist(lapply(ans,function(a)lapply(perms(b),function(v)c(a,v))),recursive=FALSE)
  ans
}
fixtures <- list(list(list(c('a','b'),c('c','d')),list(c('a','b'),c('c','d'))),list(list('a',c('b','c')),list('b',c('c','d'))),list(list('a','b','c'),list('b','a','c')))
checks <- list()
for(i in seq_along(fixtures)) {
  x<-fixtures[[i]][[1]];y<-fixtures[[i]][[2]]
  values<-unlist(lapply(orders(x),function(a)sapply(orders(y),function(b)rbo(a,b,.9,score='ext'))))
  lo<-low_rankings(x,y);hi<-hig_rankings(x,y)
  low<-unname(rbo(lo$x,lo$y,.9,score='ext'));high<-unname(rbo(hi$x,hi$y,.9,score='ext'))
  stopifnot(abs(low-min(values))<1e-12,abs(high-max(values))<1e-12)
  checks[[i]]<-data.frame(fixture=i,permutation_pairs=length(values),enumerated_min=min(values),algorithm_low=low,enumerated_max=max(values),algorithm_high=high)
}
write.table(do.call(rbind,checks),'results/RBO_EXHAUSTIVE_FIXTURE_QA.tsv',sep='\t',row.names=FALSE,quote=FALSE)
input<-read.delim('results/RBO_BLADDER_COMPLETE_BOUNDARY_PREFIXES.tsv',colClasses=c('character','character','numeric'))
plan<-read.delim('results/RBO_PAIR_PLAN.tsv',colClasses='character')
rows<-list()
for(i in seq_len(nrow(plan))) {
  a<-input[input$operator_code==plan$code_a[i],];b<-input[input$operator_code==plan$code_b[i],]
  x<-extract_ranking(a$targetId,a$operator_score);y<-extract_ranking(b$targetId,b$operator_score)
  lo<-low_rankings(x,y);hi<-hig_rankings(x,y)
  low<-rbo(lo$x,lo$y,.9);high<-rbo(hi$x,hi$y,.9);avg<-rbo(x,y,.9,ties='a')
  id<-rbo(a$targetId,b$targetId,.9)
  stopifnot(low['ext']<=avg['ext']+1e-12,avg['ext']<=high['ext']+1e-12,low['ext']<=id['ext']+1e-12,id['ext']<=high['ext']+1e-12)
  rows[[i]]<-data.frame(context_id='CCTX001',code_a=plan$code_a[i],code_b=plan$code_b[i],p=.9,nominal_depth=50,complete_prefix_a=nrow(a),complete_prefix_b=nrow(b),rbo_ext_low=unname(low['ext']),rbo_ext_id=unname(id['ext']),rbo_ext_expected_a=unname(avg['ext']),rbo_ext_high=unname(high['ext']),seen_tie_residual=unname(high['ext']-low['ext']),seen_and_unseen_lower=unname(low['min']),seen_and_unseen_upper=unname(high['max']),selection_reason=plan$selection_reason[i])
  write.table(do.call(rbind,rows),'results/RBO_REAL_BLADDER_COMPARISONS.tsv',sep='\t',row.names=FALSE,quote=FALSE)
  cat('completed pair',i,'\n');flush.console()
}
writeLines(c('PASS: upstream algorithms matched exhaustive fixtures.','Four predefined real bladder comparisons; complete boundary blocks retained.','Persistence p=0.9. RBO_EXT bounds include seen-tie permutations under the published extrapolation.','MIN(low) and MAX(high) additionally bound unseen overlap; these are distinct uncertainty quantities.','Rankings are observed top-50 prefixes extended through the entire cutoff tie block, not complete ranked candidate universes.','No claim of an all-11408-pair RBO benchmark.'),'results/RBO_QA.txt')
