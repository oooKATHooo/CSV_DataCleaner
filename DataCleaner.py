import logging
from logging.config import fileConfig
import pandas as pd
import numpy as np
from pathlib import Path
import os
import json
from typing import Literal
from ydata_profiling import ProfileReport


os.chdir(Path(__file__).parent)
fileConfig('logging.ini')
logger = logging.getLogger()


class Specs:
    """Load the json file and set the contents
    of the dictionary as attributes"""
    def __init__(self, filename) -> None:
        with open(filename, mode="r") as f:
            self.dict = json.load(f)
            
        for key in self.dict:
            setattr(self,key,self.dict[key])
    
        
class CleanerCSV:
    """A class to read versatile csv files, clean them
    according to the specifications of a json file and
    save them as a new csv file."""
    
    def __init__(self, specification_file="default_specs.json") -> None:
        logger.debug(f"start init with {specification_file}:")
        self.specs = Specs(specification_file)
        logger.debug("specs in cleaner")
        self.df_origin = pd.read_csv(self.specs.input_file, delimiter=self.specs.delimiter)
        self.df = self.df_origin.copy()
        logger.debug("csv to DataFrame - finished.\n")
        
        # attributes for self.info():
        self.n_double_headers = None
        self.n_duplicates = None
        self.n_nan_rows = None
        self.n_outlier_rows = None
        self.whiskers = None

    def names_in_column_names(self, names:list|Literal["all"]) -> list:
        """intersection of names and columnnames.
        Warns, if a name is not a column name.

        Args:   names : list of column names or Literal "all"
        """
        if names == "all":
            return list(self.df.columns)
        elif names == []:
            return []
        elif type(names) == list:
            names_copy = names[:]
            for el in names:
                if el not in self.df.columns:
                    names_copy.remove(el)
                    logger.warning(f"\nmethod 'names_in_column_names': {el} is no column name!")   # evtl besser ValueError
            return names_copy
        else: raise TypeError("structure of column names in your json-file "
                              + "has to be a list or the Literal 'all'.")

    def drop_double_header(self) -> None:
        """removes duplicates of the header, save number of duplicates."""
        logger.debug("'drop_double_header':")
        if self.n_double_headers != None:
            logger.warning("Header-Duplicates are already removed.\n\n")
            return None
        if self.specs.drop_double_headers:
            drop_list =[]
            for i, row in self.df.iterrows():
                if (list(row) == list(self.df.columns)):
                    drop_list.append(i)
            self.df.drop(index=drop_list, inplace=True)
            self.n_double_headers = len(drop_list)
            logger.debug(f"{self.n_double_headers} removed.\n")
        else:
            logger.debug(f"method not activated.\n")
        return None

    def without_nan_rows(self) -> None:   
        """Exclusion of NaN value-containing rows, specified by the json-file"""
        logger.debug(f"'without_nan_rows':")
        
        if self.n_nan_rows != None:                 # Methode bereits durchgeführt
            logger.warning("nan-rows are already removed.\n")
            return None
        
        if not self.specs.drop_na:                  # "drop_na":false
            logger.debug("method not activated.\n")
            return None

        elif not self.specs.drop_na_how["all"]:     # "all":[]
            n = self.df.shape[0]
            col = self.names_in_column_names(self.specs.drop_na_how["any"])
            self.df.dropna(how="any", subset=col, inplace=True)
            self.n_nan_rows = n - self.df.shape[0]

        elif not self.specs.drop_na_how["any"]:     # "any":[]
            n = self.df.shape[0]
            col = self.names_in_column_names(self.specs.drop_na_how["all"])
            self.df.dropna(how="all", subset=col, inplace=True)
            self.n_nan_rows = n - self.df.shape[0]

        else:
            drop_list = []
            col_all, col_any = self.specs.drop_na_how.values()   # evtl mit map
            col_all = self.names_in_column_names(col_all)
            col_any = self.names_in_column_names(col_any)
            for i,s in self.df.iterrows():
                if all(s[col_all].isnull()) and any(s[col_any].isnull()):
                    drop_list.append(i)
            self.df.drop(index=drop_list, inplace=True)
            self.n_nan_rows = len(drop_list)

        logger.debug(f"{self.n_nan_rows} removed.\n")
        return None

    def without_duplicates(self) -> None:
        """remove row duplicates, optional of specified columns."""
        logger.debug("'without_duplicates':")
        if self.n_duplicates != None:
            logger.warning("Duplicates are already droped.\n")
            return None
        elif self.specs.drop_duplicates:
            n = self.df.shape[0]
            self.df.drop_duplicates(inplace=True)
            self.n_duplicates = n - self.df.shape[0]
            logger.debug(f"{self.n_duplicates} removed.\n")
        else:
            logger.debug("not activated.\n")
        return None

    def replace_detailed(self) -> None:
        """Replacement of characters, specified by the
        list of dicts 'replace_row_char_details' in the json-file."""
        details_list = self.specs.replace_char_details
        if details_list:
            logger.debug("replace characters:")
            for replacement in details_list:
                columns, change = replacement["col"], replacement["change"]  # (list,dict)
                columns = self.names_in_column_names(columns)
                for old,new in change.items():
                    for c in columns:
                        self.df[c] = self.df[c].str.replace(old,new)
            logger.debug("finished replacement.\n")
        else:
            logger.debug("replacement not activated.\n")
        return None

    def convert_columns_upper(self) -> None:
        """converts string-columns of self.df to upper-case."""
        logger.debug("'convert_columns_upper':")
        cols = self.names_in_column_names(self.specs.str_columns_upper)
        if not cols:
            logger.debug("nothing to convert to uppercase.\n")
            return None

        for el in cols:   
            if self.df[el].dtype == object:
                self.df[el] = self.df[el].str.upper()
            else:
                logger.warning(f"check dtype of column '{el}'.")
            logger.debug("converting columns to uppercase finished.\n")
        return None

    def remove_columns(self) -> None:
        """drop columns specified in json-file"""
        logger.debug("remove_column:")
        if self.specs.drop_row_title:
            self.df.drop(columns=self.df.columns[0],inplace=True)
            logger.info("droped first column.")

        for column in self.specs.drop_col:
            try:
                self.df.drop(columns=column,inplace=True)
                logger.info(f"droped column {column}.")
            except:
                logger.warning(f"could not drop column {column}.")
        logger.debug("finished with remove_column.\n")

    def data_type_corrections(self) -> None:
        d = self.specs  # alias for better overview
        # datetime:
        for el in self.names_in_column_names(d.datetime_col):
            try:
                self.df[el] = pd.to_datetime(self.df[el],format='mixed')
                logger.debug(f"{el} could be converted as a date.")
            except:
                logger.error(f"Column {el} is not the right date-format.")
        
        # int:      # try / except... für debugging
        self.df[d.int_col] = self.df[d.int_col].astype(float).astype(int)
        # float:    # option round einführen??
        self.df[d.float_col] = self.df[d.float_col].astype(float)
        # numeric:
        for c in self.names_in_column_names(d.numeric_col):
            try:
                self.df[c] = pd.to_numeric(self.df[c], errors="raise")
                logger.debug(f"converted column {c} to numeric.")
            except:
                logger.warning(f"could not convert column {c} to numeric.")
        logger.debug("finished datatype corrections.\n")

    def drop_outliers(self) -> None:
        """remove outliers of specified columns."""
        logger.debug("outliers:")
        if self.whiskers != None:
            logger.warning("outliers are already removed.\n")
            return None
        
        self.whiskers = {}
        n = self.df.shape[0]
        columns = self.names_in_column_names(self.specs.outliers_col)
        for col in columns:
            q1 = self.df[col].quantile(0.25)
            q3 = self.df[col].quantile(0.75)
            iqr = q3 - q1
            # w0,w1 = q1 - (iqr * 1.5), q3 + (iqr * 1.5)
            # self.whiskers[col] = (w0,w1)
            self.whiskers[col] = (q1 - (iqr * 1.5), q3 + (iqr * 1.5))
        for col in columns:
            w0,w1 = self.whiskers[col]
            self.df = self.df[(self.df[col]>=w0) & (self.df[col]<=w1)]
        self.n_outlier_rows = n - self.df.shape[0]
        logger.debug(f"removed {self.n_outlier_rows} rows.\n")
        return None

    def create_profiles(self) -> None:
        """Create profiles of origin and cleaned data,
        if activated in the specification file."""
        logger.debug("create_profiles:")
        if self.specs.create_profiles:
            profile = ProfileReport(self.df_origin,title="Origin")
            logger.debug("created profile of origin.")
            profile.to_file(self.specs.input_file_profile)
            logger.debug("saved profile of origin.")

            profile = ProfileReport(self.df,title="Cleaned")
            logger.debug("created profile of cleaned data.")
            profile.to_file(self.specs.output_file_profile)
            logger.debug("saved profile of cleaned data.\n")
        else:
            logger.debug("not activated.\n")
        return None

    def save_as_csv(self) -> None:
        """save the data from DataFrame to csv."""
        logger.debug("'save_as_csv':")
        if self.specs.export_output_file:
            try:
                self.df.to_csv(self.specs.output_file, sep=self.specs.delimiter)
                logger.debug("saved cleaned data.\n")
            except:
                logger.warning("could not save as file.\n")
        else:
            logger.debug("not activated.\n")
        return None
    
    def info(self) -> None|str:
        """print information about the cleaning process"""
        info_string = ("="*30 + " Info " + "="*30 +"\n"
            f"\tHeader Duplicates:   \t{self.n_double_headers}\n"
            f"\tremoved nan rows:    \t{self.n_nan_rows}\n"
            f"\tother row Duplicates:\t{self.n_duplicates}\n"
            f"\tremoved outlier rows:\t{self.n_outlier_rows}\n"
            f"\twhiskers of specific columns:  {self.whiskers}\n\n"
            + "="*30 + " dtypes " + "="*28 + "\n" + str(self.df.dtypes) + "\n\n"
            + "="*30 + " df.head() " + "="*25 + "\n" + str(self.df.head()))

        if self.specs.export_output_file:
            with open(self.specs.cleaning_info_file, mode="w") as f:
                f.write(info_string)
        else:
            return info_string

    def specific_cleaning(self):
        """load, clean and save data from csv-file
        as specified in associated json-file."""
        d = self.specs              # alias für bessere Ünersicht

        # remove disturbing elements:
        self.drop_double_header()
        self.remove_columns()
        self.without_nan_rows()
        self.without_duplicates()
        
        # data types:
        self.data_type_corrections()

        # changes in string columns:
        self.replace_detailed()
        self.convert_columns_upper()
                
        # outliers:
        self.drop_outliers()
        
        # profiling:
        self.create_profiles()
        
        # save cleaned data:
        self.save_as_csv()

        # information about cleaning process:
        self.info()

        logger.debug("finished specific_cleaning.\n\n" + "="*50 + "\n")
    

if __name__ == "__main__":
    cleaner = CleanerCSV("test_specs.json")
    cleaner.specific_cleaning()
