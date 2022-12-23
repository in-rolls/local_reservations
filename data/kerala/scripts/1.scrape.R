
# Gets you the URLs -------------------------------------------------------



library(here)
here:: here()

library(rvest)
library(tidyverse)
library(purrr) #multi-page
library(httr)
library(haven)

# Version 1 ---------------------------------------------------------------


urls <- paste0("https://lsgkerala.gov.in/en/lbelection/electdmemberdet/2010/", 1:3000)

safe_url_logical <- map(urls, http_error)

temp <- cbind(unlist(safe_url_logical), unlist(urls))
colnames(temp) <- c("logical","url")
temp <- as.data.frame(temp)

# Gives you the safe urls as a df column
safe_urls <- temp %>% 
     dplyr::filter(logical=="FALSE") %>%
     select(url)

save(safe_urls,file="2010_safe_urls.Rda")

########################################PROGRAM STARTS HERE ########################################
########################################FROM NOW ON JUST LOAD 2010_safe_urls.Rda ########################################

load("2010_safe_urls.Rda")
#Extract ward numbers
ward_nos <- paste0(str_sub(safe_urls$url,-3,-1),"")

store_url_ward_numbers <- paste0("https://lsgkerala.gov.in/en/lbelection/electdmemberdet/2010/", ward_nos)

# urls <- paste0("https://lsgkerala.gov.in/en/lbelection/electdmemberdet/2010/", 225:227)

# Next line creates a template for local downloads
save_here <- paste0("document_", ward_nos, ".html")
mapply(download.file, store_url_ward_numbers, save_here, timeout = 200)





local_htmls <- list.files(here(), pattern=".html")

my_local_files = lapply(local_htmls, function(x) try(read_html(x)))



get_gram <- function(url){
     webpage <- url %>%  read_html() 
     webpage %>%
          html_nodes(xpath = '//*[@id="block-zircon-content"]/a[2]') %>%
          html_text() -> temp
     webpage %>%
          html_nodes(xpath = '//*[@id="block-zircon-content"]/table') %>% 
          html_table() %>% 
          as.data.frame() %>% add_column(newcol=temp)
}

election_2010 <- purrr::map(my_local_files,get_gram)

asas <- read_html(my_local_files[[1]]) %>% 
     html_node(xpath = '//*[@id="block-zircon-content"]/a[2]') %>%
     html_text() 
     

# election_2010 <- purrr::map(store_url_ward_numbers,get_gram)
# election_2010_df <- plyr::ldply(election_2010, data.frame)

election_2010_df <- as.data.frame(election_2010_df)
save(election_2010_df,file="kerala_2010_election.Rda")


#Working attempts can ignore
# New Attempt -------------------------------------------------------------

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





        # To over come timeout ----------------------------------------------------
li <- c(1244,1245,1246,1247,1248,1249,1250,1251,1252,1253,1254,1255,1256,1257,1259,1260,1261,1262,1263,1264,1265,1266,1267,1268,1269,1270,1271,1272,1273,1274,1275,1276,1277,1278,1279,1280,1281,1282,1283,1284,1285,1286,1287)
urls2 <- paste0("https://lsgkerala.gov.in/en/lbelection/electdmemberdet/2010/", li)
save_here <- paste0("document_", li, ".html")
mapply(download.file, urls2, save_here, timeout = 200)






