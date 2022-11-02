

library('tidyverse')
library(readxl)

# library(here)
# dir <- here()
setwd("/Users/varun/Dropbox/PhD/Mumbai_Urban_Gov/Original_data/election_data")

election_2007 <- read_excel("BMC-2007_raw.xlsx")
names(election_2007) <- tolower(names(election_2007))

election_2007 <- election_2007 %>% 
     mutate_at(vars(starts_with("Party ")), as.numeric)

data <- election_2007 %>% pivot_longer(cols=starts_with("Party"))

names(data) <- tolower(names(data))
data <- data %>% select("ward no", "total votes polled", "name", "value")
election_2007 <- election_2007[,-(6:22)]

final_2007_data <- merge(data, election_2007)
final_2012_data <- read_excel("2012_scanned_data.xlsx")
final_2017_data <- read_csv("mumbai_2017.csv")


# paste0(names(data),sep=",")
# ncol(data)
