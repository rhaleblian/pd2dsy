#define SAMPLE_RATE 48000.f

#include "daisy_boards.h"

#include "c/Heavy_petal_test.hpp"

using namespace daisy;

DSY_BOARD* hardware;

int num_params;

Heavy_petal_test hv(SAMPLE_RATE);

void ProcessControls();

void audiocallback(float **in, float **out, size_t size)
{
    hv.process(in, out, size);
    ProcessControls();
}

static void sendHook(HeavyContextInterface *c, const char *receiverName, uint32_t receiverHash, const HvMessage * m) {
  // Do something with message sent from Pd patch through
  // [send receiverName @hv_event] object(s)
}

int main(void)
{
    hardware = &boardsHardware;
    
    num_params = hv.getParameterInfo(0,NULL);

    hv.setSendHook(sendHook);

    hardware->Init();

    hardware->StartAdc();
    
    hardware->StartAudio(audiocallback);
    // GENERATE POSTINIT
    for(;;)
    {
        // GENERATE INFINITELOOP
    }
}

void ProcessControls()
{
    hardware->DebounceControls();
hardware->UpdateAnalogControls();
    
    for (int i = 0; i < num_params; i++)
    {
	HvParameterInfo info;
	hv.getParameterInfo(i, &info);
	
	// GENERATE CONTROLS
	
	std::string name(info.name);

	for (int j = 0; j < DaisyNumParameters; j++){
	    if (DaisyParameters[j].name == name)
	    {
		float sig = DaisyParameters[j].Process();
		
		if (DaisyParameters[j].mode == ENCODER || DaisyParameters[j].mode == KNOB)
		    hv.sendFloatToReceiver(info.hash, sig);
		else if(sig)
		    hv.sendBangToReceiver(info.hash);
	    }
	}	
    }
}
