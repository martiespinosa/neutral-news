//
//  NewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/7/25.
//

import SwiftUI
import UIKit

struct NewsView: View {
    let news: News
    let relatedNews: [News]
    var namespace: Namespace.ID
    
    @State private var dominantColor: Color = .gray
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
//                LinearGradient(colors: [dominantColor, dominantColor.opacity(0.3), .clear], startPoint: .top, endPoint: .bottom)
//                    .ignoresSafeArea()
                
                LinearGradient(colors: [dominantColor, dominantColor.opacity(0.1)], startPoint: .top, endPoint: .bottom)
                    .ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        // TODO: Pedir permiso para usar los logos de los medios?
                        if let uiImage = UIImage(named: news.sourceMedium.pressMedia.name.normalized()) {
                            Image(uiImage: uiImage)
                                .resizable()
                                .scaledToFit()
                                .frame(height: 30)
                        } else {
                            Text(news.sourceMedium.pressMedia.name)
                                .font(.title)
                                .fontWeight(.semibold)
//                                .fontDesign(.serif)
                                .foregroundColor(.secondary)
                        }
                        
                        Text(news.title)
                            .font(.title)
                            .fontWeight(.semibold)
                            .fontDesign(.serif)
                        
                        AsyncImage(url: URL(string: news.imageUrl ?? "")) { phase in
                            switch phase {
                            case .empty:
                                ShimmerView()
                                    .frame(height: 250)
                            case .success(let image):
                                image
                                    .resizable()
                                    .scaledToFit()
                            case .failure:
                                ZStack {
                                    RoundedRectangle(cornerRadius: 16)
                                        .fill(Color.secondary.opacity(0.2))
                                    Image(systemName: "photo")
                                }
                                .font(.largeTitle)
                                .frame(height: 250)
                                .frame(maxWidth: .infinity)
                                .clipShape(.rect(cornerRadius: 16))
                            @unknown default:
                                EmptyView()
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .clipShape(.rect(cornerRadius: 16))
                        
                        Text(news.description)
//                            .fontDesign(.serif)
                        
                        if let link = URL(string: news.link) {
                            Link("Leer más en la fuente", destination: link)
//                                .fontDesign(.serif)
                        }
                        
                        Spacer()
                        
                        Text("Neutral News es independiente, no está asociado a \(news.sourceMedium.pressMedia.name) ni a ningún otro medio de comunicación.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding()
                    .frame(minHeight: geometry.size.height)
                    .task {
                        dominantColor = await getDominantColor(from: news.imageUrl)
                    }
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .scrollIndicators(.hidden)
            .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
        }
    }
}

#Preview {
    let namespace = Namespace().wrappedValue
    return NewsView(news: .mock, relatedNews: [.mock, .mock, .mock], namespace: namespace)
}
