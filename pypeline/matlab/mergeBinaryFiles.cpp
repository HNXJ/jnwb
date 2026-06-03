#include "mex.h"
#include "matrix.h"
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>

#ifdef _WIN32
    const char PATH_SEP = '\\';
#else
    const char PATH_SEP = '/';
#endif

void mergeBinaryFiles(int NUM_CHANNELS, int num_samples, std::string in_file_path, char port_letter, std::string file_name) {
        // Define the size of the chunks to read/write at a time
    const int CHUNK_SIZE = 10000; // Adjust this value as needed to fit in your memory

    // Prepare a large buffer to hold a chunk of the data in the desired format
    std::vector<int16_t> buffer(NUM_CHANNELS * CHUNK_SIZE);

    std::ofstream out_file(file_name, std::ios::binary | std::ios::out);

    if (!out_file.is_open()) {
        mexPrintf("Failed to open file: %s\n", file_name.c_str());
        mexErrMsgIdAndTxt("mergeBinaryFiles:fileError", "Could not open output file.");
    }

    // We need to keep track of the file streams to read from them in chunks
    std::vector<std::ifstream> files(NUM_CHANNELS);

    // Open all the input files
    for (int ii = 0; ii < NUM_CHANNELS; ii++) {
        std::stringstream ss;
        ss << in_file_path << PATH_SEP << "amp-" << static_cast<char>(std::toupper(port_letter)) << "-" << std::setw(3) << std::setfill('0') << ii << ".dat";
        files[ii].open(ss.str(), std::ios::binary | std::ios::in);

        if (!files[ii].is_open()) {
            mexPrintf("Failed to open file: %s\n", ss.str().c_str());
            mexErrMsgIdAndTxt("mergeBinaryFiles:fileError", "Could not open input file.");
        }
    }

    // Process the data in chunks
    for (int chunk_start = 0; chunk_start < num_samples; chunk_start += CHUNK_SIZE) {
        // Calculate the size of the current chunk
        int chunk_size = std::min(CHUNK_SIZE, num_samples - chunk_start);

        // Read a chunk from each file and put it into the correct locations in the buffer
        for (int ii = 0; ii < NUM_CHANNELS; ii++) {
            std::vector<int16_t> file_chunk(chunk_size);
            files[ii].read(reinterpret_cast<char*>(file_chunk.data()), sizeof(int16_t) * chunk_size);

            for (int jj = 0; jj < chunk_size; jj++) {
                buffer[jj * NUM_CHANNELS + ii] = file_chunk[jj];
            }
        }

        // Write the buffer to the output file
        out_file.write(reinterpret_cast<const char*>(buffer.data()), sizeof(int16_t) * NUM_CHANNELS * chunk_size);
    }

    // Close all the input files
    for (int ii = 0; ii < NUM_CHANNELS; ii++) {
        files[ii].close();
    }

    out_file.close();
}

void mexFunction(int nlhs, mxArray *plhs[], int nrhs, const mxArray *prhs[]) {
    if (nrhs != 5) {
        mexErrMsgIdAndTxt("mergeBinaryFiles:invalidNumInputs", "Five inputs required.");
    }

    if (!mxIsDouble(prhs[0]) || mxIsComplex(prhs[0]) || mxGetNumberOfElements(prhs[0]) != 1) {
        mexErrMsgIdAndTxt("processBinaryFiles:inputNotScalar", "Input 1 must be a scalar.");
    }

    if (!mxIsDouble(prhs[1]) || mxIsComplex(prhs[1]) || mxGetNumberOfElements(prhs[1]) != 1) {
        mexErrMsgIdAndTxt("processBinaryFiles:inputNotScalar", "Input 2 must be a scalar.");
    }

    if (!mxIsChar(prhs[2]) || mxGetNumberOfElements(prhs[2]) < 1) {
        mexErrMsgIdAndTxt("processBinaryFiles:inputNotString", "Input 3 must be a string.");
    }

    if (!mxIsChar(prhs[3]) || mxGetNumberOfElements(prhs[3]) != 1) {
        mexErrMsgIdAndTxt("processBinaryFiles:inputNotChar", "Input 4 must be a single character.");
    }

    if (!mxIsChar(prhs[4]) || mxGetNumberOfElements(prhs[4]) < 1) {
        mexErrMsgIdAndTxt("processBinaryFiles:inputNotString", "Input 5 must be a string.");
    }

    int NUM_CHANNELS = static_cast<int>(mxGetScalar(prhs[0]));
    int num_samples = static_cast<int>(mxGetScalar(prhs[1]));
    
    char* in_file_path_temp = mxArrayToString(prhs[2]);
    if (in_file_path_temp == nullptr) {
        mexErrMsgIdAndTxt("processBinaryFiles:conversionFailed", "Conversion to string failed for input 3.");
    }
    std::string in_file_path = std::string(in_file_path_temp);
    mxFree(in_file_path_temp);
    
    char port_letter = static_cast<char>(mxGetScalar(prhs[3]));
    
    char* file_name_temp = mxArrayToString(prhs[4]);
    if (file_name_temp == nullptr) {
        mexErrMsgIdAndTxt("processBinaryFiles:conversionFailed", "Conversion to string failed for input 5.");
    }
    std::string file_name = std::string(file_name_temp);
    mxFree(file_name_temp);
    
    mergeBinaryFiles(NUM_CHANNELS, num_samples, in_file_path, port_letter, file_name);
}
