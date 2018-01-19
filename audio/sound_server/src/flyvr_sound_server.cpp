/** @file flyvr_sound_server.c
	@brief Program for low latency audio stimuli through the sound card using ASIO.
	@author David Turner <dmturner@princeton.edu>
*/
/*
 *
 * This program is used by the Fly VR software system.
 * For more information see: https://github.com/PrincetonUniversity/fly-vr
 * Copyright (c) 2018 David Turner
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files
 * (the "Software"), to deal in the Software without restriction,
 * including without limitation the rights to use, copy, modify, merge,
 * publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR
 * ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
 * WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#include <stdio.h>
#include <math.h>
#include <stdlib.h> 
#include "portaudio.h"

#define NUM_SECONDS   (5)
#define SAMPLE_RATE   (44100)

#ifndef M_PI
#define M_PI  (3.14159265)
#endif

#define TABLE_SIZE   (100)

class Sine
{
public:
    Sine() : stream(0), left_phase(0), right_phase(0)
    {
        /* initialise sinusoidal wavetable */
        for( int i=0; i<TABLE_SIZE; i++ )
        {
            sine[i] = (float) sin( ((double)i/(double)TABLE_SIZE) * M_PI * 2. );
        }

        sprintf( message, "No Message" );
    }

    bool open(PaDeviceIndex index, unsigned long FramesPerBuffer, PaTime suggestedLatency)
    {
        PaStreamParameters outputParameters;

		// If the frames per buffers is 0, set it to be unspecififed.
		if (FramesPerBuffer == 0)
			FramesPerBuffer = paFramesPerBufferUnspecified;

        outputParameters.device = index;
        if (outputParameters.device == paNoDevice) {
            return false;
        }

        const PaDeviceInfo* pInfo = Pa_GetDeviceInfo(index);
        if (pInfo != 0)
        {
            printf("Output device name: '%s'\r", pInfo->name);
        }

        outputParameters.channelCount = 2;       /* stereo output */
        outputParameters.sampleFormat = paFloat32; /* 32 bit floating point output */
		
		if (suggestedLatency == 0.0)
			outputParameters.suggestedLatency = Pa_GetDeviceInfo(outputParameters.device)->defaultLowOutputLatency;
		else
			outputParameters.suggestedLatency = suggestedLatency;

		outputParameters.hostApiSpecificStreamInfo = NULL;

        PaError err = Pa_OpenStream(
            &stream,
            NULL, /* no input */
            &outputParameters,
            SAMPLE_RATE,
            FramesPerBuffer,//paFramesPerBufferUnspecified,
            paClipOff,      /* we won't output out of range samples so don't bother clipping them */
            &Sine::paCallback,
            this            /* Using 'this' for userData so we can cast to Sine* in paCallback method */
            );

        if (err != paNoError)
        {
            /* Failed to open stream to device !!! */
            return false;
        }

        err = Pa_SetStreamFinishedCallback( stream, &Sine::paStreamFinished );

        if (err != paNoError)
        {
            Pa_CloseStream( stream );
            stream = 0;

            return false;
        }

		printf("\nsuggestedLatency = %8.4f\n\n", outputParameters.suggestedLatency);


        return true;
    }

    bool close()
    {
        if (stream == 0)
            return false;

        PaError err = Pa_CloseStream( stream );
        stream = 0;

        return (err == paNoError);
    }


    bool start()
    {
        if (stream == 0)
            return false;

        PaError err = Pa_StartStream( stream );

        return (err == paNoError);
    }

    bool stop()
    {
        if (stream == 0)
            return false;

        PaError err = Pa_StopStream( stream );

        return (err == paNoError);
    }

	unsigned long getLastFramesPerBuffer()
	{
		return lastFramesPerBuffer;
	}

private:
    /* The instance callback, where we have access to every method/variable in object of class Sine */
    int paCallbackMethod(const void *inputBuffer, void *outputBuffer,
        unsigned long framesPerBuffer,
        const PaStreamCallbackTimeInfo* timeInfo,
        PaStreamCallbackFlags statusFlags)
    {
        float *out = (float*)outputBuffer;
        unsigned long i;

		lastFramesPerBuffer = framesPerBuffer;

        (void) timeInfo; /* Prevent unused variable warnings. */
        (void) statusFlags;
        (void) inputBuffer;

        for( i=0; i<framesPerBuffer; i++ )
        {
            *out++ = sine[left_phase];  /* left */
            *out++ = sine[right_phase];  /* right */
            left_phase += 1;
            if( left_phase >= TABLE_SIZE ) left_phase -= TABLE_SIZE;
            right_phase += 1; /* higher pitch so we can distinguish left and right. */
            if( right_phase >= TABLE_SIZE ) right_phase -= TABLE_SIZE;
        }

        return paContinue;

    }

    /* This routine will be called by the PortAudio engine when audio is needed.
    ** It may called at interrupt level on some machines so don't do anything
    ** that could mess up the system like calling malloc() or free().
    */
    static int paCallback( const void *inputBuffer, void *outputBuffer,
        unsigned long framesPerBuffer,
        const PaStreamCallbackTimeInfo* timeInfo,
        PaStreamCallbackFlags statusFlags,
        void *userData )
    {
        /* Here we cast userData to Sine* type so we can call the instance method paCallbackMethod, we can do that since 
           we called Pa_OpenStream with 'this' for userData */
        return ((Sine*)userData)->paCallbackMethod(inputBuffer, outputBuffer,
            framesPerBuffer,
            timeInfo,
            statusFlags);
    }


    void paStreamFinishedMethod()
    {
        printf( "Stream Completed: %s\n", message );
    }

    /*
     * This routine is called by portaudio when playback is done.
     */
    static void paStreamFinished(void* userData)
    {
        return ((Sine*)userData)->paStreamFinishedMethod();
    }

    PaStream *stream;
    float sine[TABLE_SIZE];
    int left_phase;
    int right_phase;
    char message[20];
	unsigned long lastFramesPerBuffer;
};

class ScopedPaHandler
{
public:
    ScopedPaHandler()
        : _result(Pa_Initialize())
    {
    }
    ~ScopedPaHandler()
    {
        if (_result == paNoError)
        {
            Pa_Terminate();
        }
    }

    PaError result() const { return _result; }

private:
    PaError _result;
};


/*******************************************************************/
int main(int argc, char **argv)
{
    Sine sine;

	unsigned long FramesPerBuffer = 0;
	PaTime suggestedLatency = 0.0;
	if (argc > 1)
		FramesPerBuffer = atoi(argv[1]);
	if (argc > 2)
		suggestedLatency = atof(argv[2]);

    printf("PortAudio Test: output sine wave. SR = %d, BufSize = %d\n", SAMPLE_RATE, FramesPerBuffer);
    
    ScopedPaHandler paInit;
    if( paInit.result() != paNoError ) goto error;

    if (sine.open(Pa_GetDefaultOutputDevice(), FramesPerBuffer, suggestedLatency))
    {
        if (sine.start())
        {
            printf("Play for %d seconds.\n", NUM_SECONDS );
            
			Pa_Sleep( NUM_SECONDS * 5000 );

			printf("LastFramesPerBuffer = %d\n", sine.getLastFramesPerBuffer());

            sine.stop();
        }

        sine.close();
    }

    printf("Test finished.\n");
    return paNoError;

error:
    fprintf( stderr, "An error occured while using the portaudio stream\n" );
    fprintf( stderr, "Error number: %d\n", paInit.result() );
    fprintf( stderr, "Error message: %s\n", Pa_GetErrorText( paInit.result() ) );
    return 1;
}
