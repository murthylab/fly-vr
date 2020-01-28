function varargout = ConfigureProjector(varargin)
% CONFIGUREPROJECTOR MATLAB code for ConfigureProjector.fig
%      CONFIGUREPROJECTOR, by itself, creates a new CONFIGUREPROJECTOR or raises the existing
%      singleton*.
%
%      H = CONFIGUREPROJECTOR returns the handle to a new CONFIGUREPROJECTOR or the handle to
%      the existing singleton*.
%
%      CONFIGUREPROJECTOR('CALLBACK',hObject,eventData,handles,...) calls the local
%      function named CALLBACK in CONFIGUREPROJECTOR.M with the given input arguments.
%
%      CONFIGUREPROJECTOR('Property','Value',...) creates a new CONFIGUREPROJECTOR or raises the
%      existing singleton*.  Starting from the left, property value pairs are
%      applied to the GUI before ConfigureProjector_OpeningFcn gets called.  An
%      unrecognized property name or invalid value makes property application
%      stop.  All inputs are passed to ConfigureProjector_OpeningFcn via varargin.
%
%      *See GUI Options on GUIDE's Tools menu.  Choose "GUI allows only one
%      instance to run (singleton)".
%
% See also: GUIDE, GUIDATA, GUIHANDLES

% Edit the above text to modify the response to help ConfigureProjector

% Last Modified by GUIDE v2.5 27-Nov-2018 18:21:14

% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
                   'gui_Singleton',  gui_Singleton, ...
                   'gui_OpeningFcn', @ConfigureProjector_OpeningFcn, ...
                   'gui_OutputFcn',  @ConfigureProjector_OutputFcn, ...
                   'gui_LayoutFcn',  [] , ...
                   'gui_Callback',   []);
if nargin && ischar(varargin{1})
    gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
    [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
    gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT

global h4 seth4
% h4=NaN;
% disp(h4);

% --- Executes just before ConfigureProjector is made visible.
function ConfigureProjector_OpeningFcn(hObject, eventdata, handles, varargin)
% This function has no output args, see OutputFcn.
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
% varargin   command line arguments to ConfigureProjector (see VARARGIN)

% Choose default command line output for ConfigureProjector
handles.output = hObject;

% Update handles structure
guidata(hObject, handles);
global seth4
seth4 = [];

% UIWAIT makes ConfigureProjector wait for user response (see UIRESUME)
% uiwait(handles.figure1);


% --- Outputs from this function are returned to the command line.
function varargout = ConfigureProjector_OutputFcn(hObject, eventdata, handles) 
% varargout  cell array for returning output args (see VARARGOUT);
% hObject    handle to figure
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Get default command line output from handles structure
varargout{1} = handles.output;


% --- Executes on button press in regenerateStim.
function regenerateStim_Callback(hObject, eventdata, handles)
global h4 seth4
% hObject    handle to regenerateStim (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
    screenRadius_ = str2num(get(handles.screenRadius,'String'));
    screenX_ = str2num(get(handles.screenX,'String'));
    screenY_ = str2num(get(handles.screenY,'String'));
    screenZ_ = str2num(get(handles.screenZ,'String'));
    
    mirrorRadius_ = str2num(get(handles.mirrorRadius,'String'));
    mirrorX_ = str2num(get(handles.mirrorX,'String'));
    mirrorY_ = str2num(get(handles.mirrorY,'String'));
    mirrorZ_ = str2num(get(handles.mirrorZ,'String'));
    
    projectorX_ = str2num(get(handles.projectorX,'String'));
    projectorY_ = str2num(get(handles.projectorY,'String'));
    projectorZ_ = str2num(get(handles.projectorZ,'String'));
    
    x0_ = str2num(get(handles.x0,'String'));
    y0_ = str2num(get(handles.y0,'String'));
    x1_ = str2num(get(handles.x1,'String'));
    y1_ = str2num(get(handles.y1,'String'));
    x2_ = str2num(get(handles.x2,'String'));
    y2_ = str2num(get(handles.y2,'String'));

%     seth4
    if isempty(seth4)
        seth4 = 1;
        h4=figure('OuterPosition',[10 10 684 608]);
%         disp('ok?')
    end
    h4 = generateDome(screenRadius_,screenX_,screenY_,screenZ_, mirrorRadius_,mirrorX_,mirrorY_,mirrorZ_, projectorX_,projectorY_,projectorZ_, ...
        x0_,y0_,x1_,y1_,x2_,y2_,h4);
        



function mirrorRadius_Callback(hObject, eventdata, handles)
% hObject    handle to mirrorRadius (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of mirrorRadius as text
%        str2double(get(hObject,'String')) returns contents of mirrorRadius as a double


% --- Executes during object creation, after setting all properties.
function mirrorRadius_CreateFcn(hObject, eventdata, handles)
% hObject    handle to mirrorRadius (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function screenRadius_Callback(hObject, eventdata, handles)
% hObject    handle to screenRadius (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of screenRadius as text
%        str2double(get(hObject,'String')) returns contents of screenRadius as a double


% --- Executes during object creation, after setting all properties.
function screenRadius_CreateFcn(hObject, eventdata, handles)
% hObject    handle to screenRadius (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function screenX_Callback(hObject, eventdata, handles)
% hObject    handle to screenX (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of screenX as text
%        str2double(get(hObject,'String')) returns contents of screenX as a double


% --- Executes during object creation, after setting all properties.
function screenX_CreateFcn(hObject, eventdata, handles)
% hObject    handle to screenX (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function screenY_Callback(hObject, eventdata, handles)
% hObject    handle to screenY (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of screenY as text
%        str2double(get(hObject,'String')) returns contents of screenY as a double


% --- Executes during object creation, after setting all properties.
function screenY_CreateFcn(hObject, eventdata, handles)
% hObject    handle to screenY (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function screenZ_Callback(hObject, eventdata, handles)
% hObject    handle to screenZ (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of screenZ as text
%        str2double(get(hObject,'String')) returns contents of screenZ as a double


% --- Executes during object creation, after setting all properties.
function screenZ_CreateFcn(hObject, eventdata, handles)
% hObject    handle to screenZ (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function mirrorX_Callback(hObject, eventdata, handles)
% hObject    handle to mirrorX (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of mirrorX as text
%        str2double(get(hObject,'String')) returns contents of mirrorX as a double


% --- Executes during object creation, after setting all properties.
function mirrorX_CreateFcn(hObject, eventdata, handles)
% hObject    handle to mirrorX (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function mirrorY_Callback(hObject, eventdata, handles)
% hObject    handle to mirrorY (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of mirrorY as text
%        str2double(get(hObject,'String')) returns contents of mirrorY as a double


% --- Executes during object creation, after setting all properties.
function mirrorY_CreateFcn(hObject, eventdata, handles)
% hObject    handle to mirrorY (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function mirrorZ_Callback(hObject, eventdata, handles)
% hObject    handle to mirrorZ (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of mirrorZ as text
%        str2double(get(hObject,'String')) returns contents of mirrorZ as a double


% --- Executes during object creation, after setting all properties.
function mirrorZ_CreateFcn(hObject, eventdata, handles)
% hObject    handle to mirrorZ (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function projectorX_Callback(hObject, eventdata, handles)
% hObject    handle to projectorX (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of projectorX as text
%        str2double(get(hObject,'String')) returns contents of projectorX as a double


% --- Executes during object creation, after setting all properties.
function projectorX_CreateFcn(hObject, eventdata, handles)
% hObject    handle to projectorX (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function projectorY_Callback(hObject, eventdata, handles)
% hObject    handle to projectorY (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of projectorY as text
%        str2double(get(hObject,'String')) returns contents of projectorY as a double


% --- Executes during object creation, after setting all properties.
function projectorY_CreateFcn(hObject, eventdata, handles)
% hObject    handle to projectorY (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function projectorZ_Callback(hObject, eventdata, handles)
% hObject    handle to projectorZ (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of projectorZ as text
%        str2double(get(hObject,'String')) returns contents of projectorZ as a double


% --- Executes during object creation, after setting all properties.
function projectorZ_CreateFcn(hObject, eventdata, handles)
% hObject    handle to projectorZ (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function x0_Callback(hObject, eventdata, handles)
% hObject    handle to x0 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of x0 as text
%        str2double(get(hObject,'String')) returns contents of x0 as a double


% --- Executes during object creation, after setting all properties.
function x0_CreateFcn(hObject, eventdata, handles)
% hObject    handle to x0 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function y0_Callback(hObject, eventdata, handles)
% hObject    handle to y0 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of y0 as text
%        str2double(get(hObject,'String')) returns contents of y0 as a double


% --- Executes during object creation, after setting all properties.
function y0_CreateFcn(hObject, eventdata, handles)
% hObject    handle to y0 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function x1_Callback(hObject, eventdata, handles)
% hObject    handle to x1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of x1 as text
%        str2double(get(hObject,'String')) returns contents of x1 as a double


% --- Executes during object creation, after setting all properties.
function x1_CreateFcn(hObject, eventdata, handles)
% hObject    handle to x1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function y1_Callback(hObject, eventdata, handles)
% hObject    handle to y1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of y1 as text
%        str2double(get(hObject,'String')) returns contents of y1 as a double


% --- Executes during object creation, after setting all properties.
function y1_CreateFcn(hObject, eventdata, handles)
% hObject    handle to y1 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function x2_Callback(hObject, eventdata, handles)
% hObject    handle to x2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of x2 as text
%        str2double(get(hObject,'String')) returns contents of x2 as a double


% --- Executes during object creation, after setting all properties.
function x2_CreateFcn(hObject, eventdata, handles)
% hObject    handle to x2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end



function y2_Callback(hObject, eventdata, handles)
% hObject    handle to y2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)

% Hints: get(hObject,'String') returns contents of y2 as text
%        str2double(get(hObject,'String')) returns contents of y2 as a double


% --- Executes during object creation, after setting all properties.
function y2_CreateFcn(hObject, eventdata, handles)
% hObject    handle to y2 (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    empty - handles not created until after all CreateFcns called

% Hint: edit controls usually have a white background on Windows.
%       See ISPC and COMPUTER.
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end


% --- Executes on button press in saveCoords.
function saveCoords_Callback(hObject, eventdata, handles)
% hObject    handle to saveCoords (see GCBO)
% eventdata  reserved - to be defined in a future version of MATLAB
% handles    structure with handles and user data (see GUIDATA)
    screenRadius_ = str2num(get(handles.screenRadius,'String'));
    screenX_ = str2num(get(handles.screenX,'String'));
    screenY_ = str2num(get(handles.screenY,'String'));
    screenZ_ = str2num(get(handles.screenZ,'String'));
    
    mirrorRadius_ = str2num(get(handles.mirrorRadius,'String'));
    mirrorX_ = str2num(get(handles.mirrorX,'String'));
    mirrorY_ = str2num(get(handles.mirrorY,'String'));
    mirrorZ_ = str2num(get(handles.mirrorZ,'String'));
    
    projectorX_ = str2num(get(handles.projectorX,'String'));
    projectorY_ = str2num(get(handles.projectorY,'String'));
    projectorZ_ = str2num(get(handles.projectorZ,'String'));
    
    x0_ = str2num(get(handles.x0,'String'));
    y0_ = str2num(get(handles.y0,'String'));
    x1_ = str2num(get(handles.x1,'String'));
    y1_ = str2num(get(handles.y1,'String'));
    x2_ = str2num(get(handles.x2,'String'));
    y2_ = str2num(get(handles.y2,'String'));
    
    save('coords.mat','screenRadius_','screenX_','screenY_','screenZ_', 'mirrorRadius_','mirrorX_','mirrorY_','mirrorZ_', 'projectorX_','projectorY_','projectorZ_', ...
                 'x0_','y0_','x1_','y1_','x2_','y2_');
