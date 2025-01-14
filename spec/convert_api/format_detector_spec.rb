RSpec.describe ConvertApi::FormatDetector, '#run' do
  subject { described_class.new(resource, to_format).run }

  let(:to_format) { 'pdf' }

  context 'with file name' do
    let(:resource) { 'test.txt' }
    it { is_expected.to eq('txt') }
  end

  context 'when archiving' do
    let(:resource) { 'test.txt' }
    let(:to_format) { 'zip' }
    it { is_expected.to eq('any') }
  end

  context 'with file path' do
    let(:resource) { '/some/path/test.txt' }
    it { is_expected.to eq('txt') }
  end

  context 'with url' do
    let(:resource) { 'https://hostname/some/path/test.txt?test=1' }
    it { is_expected.to eq('txt') }
  end

  context 'with File' do
    let(:resource) { File.open('examples/files/test.docx') }
    it { is_expected.to eq('docx') }
  end

  context 'with UploadIO' do
    let(:resource) { ConvertApi::UploadIO.new('test', 'file.txt') }
    let(:upload_result) { { 'FileId' => '123', 'FileExt' => 'txt', 'FileName' => 'file.txt' } }

    before { expect(ConvertApi.client).to receive(:upload).and_return(upload_result) }

    it { is_expected.to eq('txt') }
  end

  context 'when path without extension' do
    let(:resource) { 'test' }

    it 'raises error' do
      expect { subject }.to raise_error(ConvertApi::FormatError)
    end
  end
end
