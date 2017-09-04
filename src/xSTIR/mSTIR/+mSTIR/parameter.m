function value = parameter(handle, set, name, type)
    hv = calllib('mstir', 'mSTIR_parameter', handle, set, name);
    mUtilities.check_status('parameter', hv)
    if strcmp(type, 'i')
        value = calllib('mutilities', 'mIntDataFromHandle', hv);
    elseif strcmp(type, 'f')
        value = calllib('mutilities', 'mFloatDataFromHandle', hv);
    end
end