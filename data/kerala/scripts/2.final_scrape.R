library(here)
here:: here()
library(rvest)
library(tidyverse)
library(purrr) #multi-page
library(httr)
library(haven)
# New Attempt -------------------------------------------------------------

# Uses the downloaded files to organise the DF.  (Change year as n --------

#Note to self, write a loop to do all years in one pass.

load("2010_safe_urls.Rda")
ward_nos <- as.data.frame(paste0(str_sub(safe_urls$url,-3,-1),""))

# index <-as.data.frame(ward_nos)
urls <- paste0("https://lsgkerala.gov.in/en/lbelection/electdmemberdet/2010/", 1:1288)
get_gram <- function(url){
        Sys.sleep(.1)
        tryCatch({
        webpage <- url %>%  read_html() 
        webpage %>%
                html_nodes(xpath = '//*[@id="block-zircon-content"]/a[2]') %>%
                html_text() -> temp
        webpage %>%
                html_nodes(xpath = '//*[@id="block-zircon-content"]/table') %>% 
                html_table() %>% 
                as.data.frame() %>% add_column(newcol=temp)
        }, error = function(e){ 
                NULL
        })
}

temp_result <- purrr::map(urls,get_gram)
result <- do.call(rbind.data.frame, temp_result)




