# Narrow base-R compatibility layer for the verbs used by the pinned upstream
# low.R/hig.R functions. The upstream mathematical algorithms are not rewritten.
# Used because installed dplyr (built for R 4.6.1) crashes this R 4.6.0 at exit.
bind_cols <- function(x) as.data.frame(x, stringsAsFactors=FALSE)
full_join <- function(x,y,by) merge(x,y,by.x=names(by),by.y=unname(by),all=TRUE,sort=FALSE,suffixes=c('.x','.y'))
mutate <- function(.data,...) {
  expressions<-as.list(substitute(list(...)))[-1]
  for(n in names(expressions)) .data[[n]]<-eval(expressions[[n]],.data,parent.frame())
  .data
}
desc <- function(x) -x
arrange <- function(.data,...) {
  expressions<-as.list(substitute(list(...)))[-1]
  values<-lapply(expressions,eval,envir=.data,enclos=parent.frame())
  .data[do.call(order,c(values,list(na.last=TRUE,method='radix'))),,drop=FALSE]
}
filter <- function(.data,...) {
  expressions<-as.list(substitute(list(...)))[-1]
  tests<-lapply(expressions,eval,envir=.data,enclos=parent.frame())
  keep<-Reduce(`&`,tests);keep[is.na(keep)]<-FALSE
  .data[keep,,drop=FALSE]
}
pull <- function(.data,var) .data[[as.character(substitute(var))]]
slice <- function(.data,...) .data[c(...),,drop=FALSE]
source_without_dplyr <- function(path) {
  for(expr in parse(path)) {
    if(is.call(expr)&&identical(expr[[1]],as.name('library'))) {
      stopifnot(identical(expr[[2]],as.name('dplyr')))
    } else eval(expr,envir=.GlobalEnv)
  }
}
