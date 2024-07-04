

def convert_str_percent_to_float(current_level_of_physical_realization_of_the_work):
    _percent = 0.0
    _current_level_of_physical_realization_of_the_works = str(current_level_of_physical_realization_of_the_work).split("%") if current_level_of_physical_realization_of_the_work else []
    if _current_level_of_physical_realization_of_the_works:
        _current_level_of_physical_realization_of_the_work = _current_level_of_physical_realization_of_the_works[0]
        if not _current_level_of_physical_realization_of_the_work \
                or not str(_current_level_of_physical_realization_of_the_work).replace('.','',1).replace(',','',1).isdigit():
            _percent = 0.0
        else:
            _percent = float(_current_level_of_physical_realization_of_the_work.replace(',', '0'))
            
    return _percent