//
//  MirrorModel.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 2/8/25.
//

import CoreML

class MirrorModel {
    private var model: MirrorML?
    
    init() {
        do {
            let config = MLModelConfiguration()
            self.model = try MirrorML(configuration: config)
            print("Modelo cargado correctamente.")
        } catch {
            print("Error al cargar el modelo: \(error.localizedDescription)")
        }
    }
    
    func predict(inputText: String) -> [Float]? {
        guard let model = model else {
            print("Modelo no cargado.")
            return nil
        }
        
        guard let input = convertToModelInput(inputText: inputText) else {
            print("Error al convertir la entrada.")
            return nil
        }
        
        do {
            let prediction = try model.prediction(input: input)
            
            if let multiArray = prediction.var_519 as? MLMultiArray {
                let embeddings = convertMLMultiArrayToFloatArray(multiArray)
                return embeddings
            } else {
                print("No se pudieron extraer los embeddings de la predicción.")
                return nil
            }
        } catch {
            print("Error en la predicción: \(error.localizedDescription)")
            return nil
        }
    }
    
    private func convertMLMultiArrayToFloatArray(_ multiArray: MLMultiArray) -> [Float] {
        var floatArray: [Float] = []
        for i in 0..<multiArray.count {
            if let value = multiArray[i] as? NSNumber {
                floatArray.append(value.floatValue)
            }
        }
        return floatArray
    }
    
    private func convertToModelInput(inputText: String) -> MirrorMLInput? {
        let tokens = tokenize(text: inputText)
        guard let inputIDs = createMultiArray(from: tokens, shape: [1, 128]),
              let attentionMask = createMultiArray(from: tokens, shape: [1, 128]) else {
            print("Error creando los arrays.")
            return nil
        }
        
        return MirrorMLInput(input_ids: inputIDs, attention_mask: attentionMask)
    }
    
    func tokenize(text: String) -> [Int] {
        // Aquí puedes usar una tokenización más adecuada
        let words = text.lowercased().components(separatedBy: " ")
        let maxTokens = 128
        return Array(words.prefix(maxTokens)).map { _ in Int.random(in: 1...1000) }
    }
    
    private func createMultiArray(from tokens: [Int], shape: [NSNumber]) -> MLMultiArray? {
        do {
            let array = try MLMultiArray(shape: shape, dataType: .int32)
            for i in 0..<tokens.count {
                array[i] = NSNumber(value: tokens[i])
            }
            return array
        } catch {
            print("Error creando MLMultiArray: \(error)")
            return nil
        }
    }
    
    private func cosineSimilarity(_ vector1: [Float], _ vector2: [Float]) -> Float {
        let dotProduct = zip(vector1, vector2).map { $0 * $1 }.reduce(0, +)
        let magnitude1 = sqrt(vector1.map { $0 * $0 }.reduce(0, +))
        let magnitude2 = sqrt(vector2.map { $0 * $0 }.reduce(0, +))
        return dotProduct / (magnitude1 * magnitude2)
    }
    
    func processMultipleNews(newsArray: [News], similarityThreshold: Float = 0.95) -> [[News]] {
        print("Procesando noticias...")
        var groupedNews = [[News]]()
        var embeddingsArray: [[Float]] = []
        
        for news in newsArray {
            if let embedding = self.predict(inputText: news.description) {
                embeddingsArray.append(embedding)
            } else {
                print("No se pudo obtener embedding para: \(news)")
            }
        }
        
        for (index, embedding) in embeddingsArray.enumerated() {
            var isGrouped = false
            for i in 0..<groupedNews.count {
                let groupEmbedding = embeddingsArray[i]
                if cosineSimilarity(embedding, groupEmbedding) >= similarityThreshold {
                    groupedNews[i].append(newsArray[index])
                    isGrouped = true
                    break
                }
            }
            if !isGrouped {
                groupedNews.append([newsArray[index]])
            }
        }
        
        return groupedNews
    }
}
